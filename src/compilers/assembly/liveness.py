from assembly.common import *
from assembly.graph import Graph
import assembly.tac_ast as tac
import copy

def instrDef(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers defined by some instrucution.
    """
    defs: set[tac.ident] = set()
    
    match instr:
        case tac.Assign(var):
            defs.add(var)
        case tac.Call(var):
            if var is not None:
                defs.add(var)
        case tac.GotoIf(): 
            pass
        case tac.Goto():
            pass
        case tac.Label():
            pass
    
    return defs

def instrUse(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers used by some instrucution.
    """
    uses: set[tac.ident] = set()
    
    match instr:
        case tac.Assign(_, left):
            uses = uses.union(expUse(left))
        case tac.Call(_, name, args):
            if "print" in name.name:
                for arg in args:
                    if isinstance(arg, tac.Name):
                        uses.add(arg.var)
        case tac.GotoIf(test): 
            if isinstance(test, tac.Name):
                uses.add(test.var)
        case tac.Goto():
            pass
        case tac.Label():
            pass

    return uses

def expUse(exp: tac.exp) -> set[tac.ident]:
    """
    Returns the set of Identifiers used in some expression
    """
    uses: set[tac.ident] = set()
    
    match exp:
        case tac.Prim(prim):
            if isinstance(prim, tac.Name):
                uses.add(prim.var)
        case tac.BinOp(left, _, right):
            if isinstance(left, tac.Name):
                uses.add(left.var)
            if isinstance(right, tac.Name):
                uses.add(right.var)
    
    return uses

# Each individual instruction has an identifier. This identifier is the tuple
# (index of basic block, index of instruction inside the basic block)
type InstrId = tuple[int, int]

class InterfGraphBuilder:
    def __init__(self):
        # self.before holds, for each instruction I, to set of variables live before I.
        self.before: dict[InstrId, set[tac.ident]] = {}
        # self.after holds, for each instruction I, to set of variables live after I.
        self.after: dict[InstrId, set[tac.ident]] = {}

    def __liveStart(self, bb: BasicBlock, s: set[tac.ident]) -> set[tac.ident]:
        """
        Given a set of variables s and a basic block bb, __liveStart computes
        the set of variables live at the beginning of bb, assuming that s
        are the variables live at the end of the block.

        Essentially, you have to implement the subalgorithm "Computing L_start" from
        slide 46 here. You should update self.after and self.before while traversing
        the instructions of the basic block in reverse.
        """
        
        # number of instructions in block
        n = len(bb.instrs)
        
        # which block
        block_idx = bb.index
        
        # start at the bottom and work to the top
        instr_idx = len(bb.instrs) -1
        for instr in reversed(bb.instrs):
            # If last instruction -> after is the input to the next block
            if instr_idx + 1 == n:
                self.after[(block_idx, instr_idx)] = s

            # Else after is the input to the next instruction
            else: 
                self.after[(block_idx, instr_idx)] = self.before[(block_idx, instr_idx+1)]
            
            # calculate new before value for the instruction
            new_before: set[tac.ident] = copy.deepcopy(self.after[(block_idx, instr_idx)])
            new_before.difference_update(instrDef(instr))
            new_before = new_before.union(instrUse(instr))
            
            self.before[(block_idx, instr_idx)] = new_before

            instr_idx -= 1
            
        # Return the input to the block
        return self.before.get((block_idx, 0), set())
        
    
    def __liveness(self, g: ControlFlowGraph):
        """+
        This method computes liveness information and fills the sets self.before and
        self.after.

        You have to implement the algorithm for computing liveness in a CFG from
        slide 46 here.
        """
        
        # Inputs to the blocks
        IN: dict[int, set[tac.Ident]] = {}
        
        # Add sets to all basic blocks in dict
        for bb in list(g.vertices):
            IN[bb] = set()
        
        # Until nothing changes        
        while True:
            # Make a copy of the input
            in_check = copy.deepcopy(IN)
            
            # go through the vertices in reverse
            for vert in reversed(list(g.vertices)):
                out: set[tac.ident] = set()
                
                # get all inputs for the successors of the current block
                for succ in g.succs(vert):
                    if g.getData(succ).instrs:
                        out = out.union(IN[succ])
                
                # calc l_start for current block        
                IN[vert] = self.__liveStart(g.getData(vert), out)
                
            if in_check == IN:
                break
        
        
            
    def __addEdgesForInstr(self, instrId: InstrId, instr: tac.instr, interfG: InterfGraph):
        """
        Given an instruction and its ID, adds the edges resulting from the instruction
        to the interference graph.

        You should implement the algorithm specified on the slide
        "Computing the interference graph" (slide 50) here.
        """
        
        defs = instrDef(instr)
        
        after_instr = self.after.get(instrId)
        
        # go through all defined variables in the instruction
        for d in defs:
            if after_instr is not None:
                for i in after_instr:
                    
                    # all output defs for the instruction with d should have an edge with d
                    if d.name != i.name:
                        if not interfG.hasVertex(d):
                            interfG.addVertex(d, None)
                        if not interfG.hasVertex(i):
                            interfG.addVertex(i, None)
                            
                        interfG.addEdge(d, i)

    def build(self, g: ControlFlowGraph) -> InterfGraph:
        """
        This method builds the interference graph. It performs three steps:

        - Use __liveness to fill the sets self.before and self.after.
        - Setup the interference graph as an undirected graph containing all variables
          defined or used by any instruction of any basic block. Initially, the
          graph does not have any edges.
        - Use __addEdgesForInstr to fill the edges of the interference graph.
        """
        
        inter_graph: InterfGraph = Graph[tac.ident, None]("undirected")
        
        self.__liveness(g)
        for vert in g.vertices:
            
            for i, instr in enumerate(list(g.getData(vert).instrs)):
                self.__addEdgesForInstr((vert,i), instr, inter_graph)
        
        return inter_graph
            
def buildInterfGraph(g: ControlFlowGraph) -> InterfGraph:
    builder = InterfGraphBuilder()
    
    graph = builder.build(g)
    return graph