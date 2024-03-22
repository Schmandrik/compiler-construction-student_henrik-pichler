from lang_var.var_ast import (
    stmt,
    mod,
    StmtExp,
    Assign,
    Call,
    exp,
    IntConst,
    Name,
    UnOp,
    BinOp,
    binaryop,
    Add,
    Sub,
    Mul,
    USub,
)

from common.wasm import (
    WasmInstr,
    WasmModule,
    WasmFuncTable,
    WasmInstrConst,
    WasmFunc,
    WasmId,
    WasmInstrCall,
    WasmExport,
    WasmExportFunc,
    WasmInstrVarLocal,
    WasmInstrNumBinOp,
    WasmInstrVarDef,
)

import lang_var.var_tychecker as var_tychecker
from common.compilerSupport import wasmImports, CompilerConfig


def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Function to compile the lang_var module
    """

    # Type Check module
    vars = var_tychecker.tycheckModule(m)

    # Initialze instruction list
    wasm_instr: list[WasmInstr] = []

    # Define local variables
    for var in vars:
        wasm_instr.append(WasmInstrVarDef(WasmId(f"${var.name}"), "i64"))

    # Compile module statements
    wasm_instr.extend(compileStmts(m.stmts))

    # Create main function
    main = WasmFunc(
        id=WasmId("$main"), params=[], result=None, locals=[], instrs=wasm_instr
    )

    # Create compiled module
    compiled_module = WasmModule(
        imports=wasmImports(1),
        exports=[WasmExport("main", WasmExportFunc(WasmId("$main")))],
        globals=[],
        data=[],
        funcTable=WasmFuncTable([]),
        funcs=[main],
    )

    return compiled_module


def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    """
    Function to compile statements
    """

    wasm_instr: list[WasmInstr] = []

    for stmt in stmts:
        match stmt:
            case StmtExp(exp):
                comp_exp = compileExp(exp)
                wasm_instr.extend(comp_exp)
                
            case Assign(var, exp):
                wasm_instr.extend(compileExp(exp))
                wasm_instr.append(WasmInstrVarLocal("set", WasmId(f"${var.name}")))

    return wasm_instr


def compileExp(exp: exp) -> list[WasmInstr]:
    """
    Function to compile expressions
    """

    wasm_instr: list[WasmInstr] = []

    match exp:
        case IntConst(v):
            wasm_instr.append(WasmInstrConst("i64", v))
            
        case Name(name):
            wasm_instr.append(WasmInstrVarLocal("get", WasmId(f"${name.name}")))
            
        case Call(name, args):
            for arg in args:
                wasm_instr.extend(compileExp(arg))
            if name.name == "print":
                wasm_instr.append(WasmInstrCall(WasmId("$print_i64")))
            elif name.name == "input_int":
                wasm_instr.append(WasmInstrCall(WasmId("$input_i64")))
                
        case UnOp(op, arg):
            match op:
                case USub():
                    comp_arg = compileExp(arg)
                    wasm_instr.append(WasmInstrConst("i64", 0))
                    wasm_instr.extend(comp_arg)
                    wasm_instr.append(compileBinOp(Sub()))
                    
        case BinOp(left, op, right):
            wasm_instr.extend(compileExp(left))
            wasm_instr.extend(compileExp(right))
            wasm_instr.append(compileBinOp(op))

    return wasm_instr


def compileBinOp(op: binaryop) -> WasmInstrNumBinOp:
    """
    Function to compile Binary Operator
    """
    op_str = None
    match op:
        case Add():
            op_str = "add"
        case Sub():
            op_str = "sub"
        case Mul():
            op_str = "mul"

    return WasmInstrNumBinOp("i64", op_str)
