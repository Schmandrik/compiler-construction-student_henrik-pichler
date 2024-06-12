import sys
sys.path.append("./src/")
                
from assembly.loopToTac import loopToTac
from assembly import controlFlow
from common import genericCompiler as genCompiler

args = genCompiler.Args(input='./inputfortesting.py', output='./out.wasm', wat2wasm='wat2wasm', maxMemSize=None, maxArraySize=None, maxRegisters=None)

tac_instr = loopToTac(args)

ctrl_flow_graph = controlFlow.buildControlFlowGraph(tac_instr)
    
from compilers.assembly.liveness import *
from compilers.assembly.graphColoring import * 

graph = buildInterfGraph(ctrl_flow_graph)

colorInterfGraph(graph)