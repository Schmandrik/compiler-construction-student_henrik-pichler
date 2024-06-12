from assembly.common import *
import assembly.tac_ast as tac
import common.log as log
from common.prioQueue import PrioQueue
import copy

def chooseColor(x: tac.ident, forbidden: dict[tac.ident, set[int]]) -> int:
    """
    Returns the lowest possible color for variable x that is not forbidden for x.
    """
    
    forbidden_x = copy.deepcopy(forbidden.get(x, set()))
    
    ret = 0
    while True:
        if ret not in forbidden_x:
            return ret
        else: ret += 1

def adj(g: InterfGraph, ident: tac.ident) -> list[tac.ident]:
    """
    Get adjacent vertices
    """
    return g.succs(ident)

def colorInterfGraph(g: InterfGraph, secondaryOrder: dict[tac.ident, int]={},
                     maxRegs: int=MAX_REGISTERS) -> RegisterMap:
    """
    Given an interference graph, computes a register map mapping a TAC variable
    to a TACspill variable. You have to implement the "simple graph coloring algorithm"
    from slide 58 here.

    - Parameter maxRegs is the maximum number of registers we are allowed to use.
    - Parameter secondaryOrder is used by the tests to get deterministic results even
      if two variables have the same number of forbidden colors.
    """
    log.debug(f"Coloring interference graph with maxRegs={maxRegs}")
    colors: dict[tac.ident, int] = {}
    forbidden: dict[tac.ident, set[int]] = {}
    q = PrioQueue(secondaryOrder)
    
    W = {x for x in list(g.vertices)}
    for _ in range(len(list(g.vertices))):
        q = PrioQueue(secondaryOrder)
        for vert in list(W):
            occ = sum([colors.get(x, 0) for x in adj(g, vert)])
            q.push(vert, occ)
        
        next_vert = q.pop()
        next_color = chooseColor(next_vert, forbidden)
        colors[next_vert] = next_color
        
        for vert in adj(g, next_vert):
            if not forbidden.get(vert):
                forbidden[vert] = {next_color}
            else:
                forbidden[vert].add(next_color)
                
        W.remove(next_vert)
    
    m = RegisterAllocMap(colors, maxRegs)
    return m
