"""
Various functions to make it easier to build test models.
"""
from __future__ import print_function

import numpy

from openmdao.core.group import Group
from openmdao.core.parallel_group import ParallelGroup
from openmdao.core.component import Component
from openmdao.components.indep_var_comp import IndepVarComp
from openmdao.test.exec_comp_for_test import ExecComp4Test

class ABCDArrayComp(ExecComp4Test):
    def __init__(self, size, **kwargs):
        super(ABCDArrayComp, self).__init__(['c = a*1.1','d=b*0.9'],
                                            nl_delay=kwargs.get('nl_delay',.01),
                                            lin_delay=kwargs.get('lin_delay',.01),
                                            trace=kwargs.get('trace',False),
                                            a=numpy.zeros(size),
                                            b=numpy.zeros(size),
                                            c=numpy.zeros(size),
                                            d=numpy.zeros(size))

class DynComp(Component):
    def __init__(self, nparams, noutputs, nstates=0,
                 nl_sleep=0.001, ln_sleep=0.001,
                 var_factory=float, vf_args=()):
        super(DynComp, self).__init__()

        self.nl_sleep = nl_sleep
        self.ln_sleep = ln_sleep

        for i in range(nparams):
            self.add_param('p%d'%i, var_factory(*vf_args))

        for i in range(noutputs):
            self.add_output("o%d"%i, var_factory(*vf_args))

        for i in range(nstates):
            self.add_state("s%d"%i, var_factory(*vf_args))

    def solve_nonlinear(self, params, unknowns, resids):
        time.sleep(self.nl_sleep)

    def solve_linear(self, dumat, drmat, vois, mode=None):
        time.sleep(self.ln_sleep)

def create_dyncomps(parent, ncomps, nvars, nconns):
    """Create a specified number of DynComps and add them to the
    given parent and add the number of specified connections.
    """
    for i in range(ncomps):
        nparams = nvars//2
        nunknowns = nvars//2
        parent.add("C%d" % i, DynComp(nparams, nunknowns))

        if i > 0:
            for j in range(nconns):
                parent.connect("C%d.o%d" % (i-1,j), "C%d.p%d" % (i, j))

def _child_name(child, i):
    if isinstance(child, Group):
        return 'G%d'%i
    return 'C%d'%i

def build_sequence(child_factory, num_children, conns=(), parent=None):
    if parent is None:
        parent = Group()

    cnames = []
    for i in range(num_children):
        child = child_factory()
        cname = _child_name(child, i)
        parent.add(cname, child)
        if i:
            for u,v in conns:
                parent.connect('.'.join((cnames[-1],u)),
                               '.'.join((cname,v)))
        cnames.append(cname)

    return parent


if __name__ == '__main__':
    import sys
    from openmdao.core.problem import Problem
    from openmdao.devtools.debug import stats
    vec_size = 100000
    num_comps = 50
    pts = 2

    if 'petsc' in sys.argv:
        from openmdao.core.petsc_impl import PetscImpl
        impl = PetscImpl
    else:
        from openmdao.core.basic_impl import BasicImpl
        impl = BasicImpl

    g = Group()
    p = Problem(impl=impl, root=g)

    if 'gmres' in sys.argv:
        from openmdao.solvers.scipy_gmres import ScipyGMRES
        p.root.ln_solver = ScipyGMRES()

    g.add("P", IndepVarComp('x', numpy.ones(vec_size)))

    p.driver.add_desvar("P.x")

    par = g.add("par", ParallelGroup())
    for pt in range(pts):
        ptg = Group()
        par.add(_child_name(ptg, pt), ptg)
        build_sequence(lambda: ABCDArrayComp(vec_size),
                           num_comps, [('c', 'a'),('d','b')], ptg)
        g.connect("P.x", "par.%s.%s.a" % (_child_name(ptg, pt),
                                          _child_name(None, 0)))

        cname = _child_name(ptg, pt) + '.' + _child_name(None, num_comps-1)
        p.driver.add_objective("par.%s.c" % cname)
        p.driver.add_constraint("par.%s.d" % cname, lower=0.0)

    p.setup()
    p.run()
    #g.dump(verbose=True)
    p.root.list_connections()
    print("\nPts:", pts)
    print("Comps per pt:", num_comps)
    print("Var size:", vec_size)
    stats(p)
