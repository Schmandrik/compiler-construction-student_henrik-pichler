from common.wasm import (WasmInstr, WasmModule, WasmFuncTable,
                         WasmInstrConst, WasmFunc, WasmId, 
                         WasmInstrCall, WasmExport, WasmExportFunc, 
                         WasmInstrVarLocal, WasmInstrNumBinOp, WasmValtype,
                         WasmInstrIntRelOp, WasmInstrIf, WasmInstrLoop, WasmInstrBlock, WasmInstrBranch)

import lang_array.array_tychecker as array_tychecker
from common.compilerSupport import wasmImports, CompilerConfig
from lang_array.array_astAtom import *
import lang_array.array_ast as plainAst
import lang_array.array_tychecker as array_tychecker
import lang_array.array_transform as array_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *

def compileModule(m: plainAst.mod, cfg: CompilerConfig) -> WasmModule:
    """
    Function to compile the lang_var module
    """

    # Type Check module
    vars = array_tychecker.tycheckModule(m)
    var_list = list(vars.items())
    # Initialze instruction list
    locals: list[tuple[WasmId, WasmValtype]] = []

    # Define local variables
    for var, info in var_list:
        var_type = "i64" if isinstance(info.ty, Int) else "i32" 
        locals.append((WasmId(f"${var.name}"), var_type))
    
    locals.extend(Locals.decls())

    transformed_stmts: Tuple[list[array_transform.atom.stmt], array_transform.Ctx] = array_transform.transStmts(m.stmts, array_transform.Ctx())
    
    atom_stmts: list[array_transform.atom.stmt] = transformed_stmts[0]
    ctx: array_transform.Ctx = transformed_stmts[1]
    
    ctx_vars = list(ctx.freshVars.items())
    for ctx_var, ty in ctx_vars:
        var_type = "i64" if isinstance(ty, Int) else "i32" 
        locals.append((WasmId(f"${ctx_var.name}"), var_type))
    
    
    # Compile module statements
    wasm_instr: list[WasmInstr] = compileStmts(atom_stmts, cfg)

    # Create main function
    main = WasmFunc(
        id=WasmId("$main"), params=[], result=None, locals=locals, instrs=wasm_instr
    )
    
    # Create compiled module
    compiled_module = WasmModule(
        imports=wasmImports(cfg.maxMemSize),
        exports=[WasmExport("main", WasmExportFunc(WasmId("$main")))],
        data=Errors().data(),
        globals=Globals.decls(),
        funcTable=WasmFuncTable([]),
        funcs=[main],
    )

    return compiled_module


def compileStmts(stmts: list[stmt], cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Function to compile statements
    """

    wasm_instr: list[WasmInstr] = []

    for stmt in stmts:
        match stmt:
            case StmtExp(exp):
                comp_exp = compileExp(exp, cfg)
                wasm_instr.extend(comp_exp)
                
            case Assign(var, exp):
                wasm_instr.extend(compileExp(exp, cfg))
                if (isinstance(exp, Subscript) 
                    and isinstance(exp.ty, NotVoid)
                    and isinstance(exp.ty.ty, Array)):
                    wasm_instr.append(WasmInstrConvOp("i32.wrap_i64"))
                wasm_instr.append(WasmInstrVarLocal("set", WasmId(f"${var.name}")))
                
            case IfStmt(cond, if_stmt, else_stmt):
                wasm_instr.extend(compileExp(cond, cfg))
                wasm_instr.append(WasmInstrIf(None, compileStmts(if_stmt, cfg), compileStmts(else_stmt, cfg)))
            
            case WhileStmt(cond, body):
                loop_body = compileLoopBody(cond, body, cfg)
                loop: list[WasmInstr] = [WasmInstrLoop(WasmId("$loop_0_start"), loop_body)]
                wasm_instr.append(WasmInstrBlock(WasmId("$loop_0_exit"), None, loop))

            case SubscriptAssign(left, index, right):
                wasm_instr.extend(arrayOffsetInstrs(left, index))
        
                if isinstance(left.ty, Array):
                    wasm_instr.extend(compileSubscript(left.ty.elemTy))
                
                wasm_instr.extend(compileExp(right, cfg))
                if isinstance(left.ty, Array):
                    wasm_instr.append(WasmInstrMem("i32" if isinstance(left.ty.elemTy, Array) else "i64", "store"))
            
    return wasm_instr


def compileExp(exp: exp, cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Function to compile expressions
    """
    wasm_instr: list[WasmInstr] = []
    match exp:
        case AtomExp(atom_exp):
            match atom_exp:
                case IntConst(v):
                    wasm_instr.append(WasmInstrConst("i64", v))
                case BoolConst(v):
                    wasm_instr.append(WasmInstrConst("i32", int(v)))
                case Name(name):
                    wasm_instr.append(WasmInstrVarLocal("get", WasmId(f"${name.name}")))
            
        case Call():
            wasm_instr.extend(compileCall(exp, cfg))
                
        case UnOp(op, arg):
            match op:
                case USub():
                    # subtract from zero
                    comp_arg = compileExp(arg, cfg)
                    wasm_instr.append(WasmInstrConst("i64", 0))
                    wasm_instr.extend(comp_arg)
                    wasm_instr.append(WasmInstrNumBinOp("i64", "sub"))
                case Not():
                    # compare to zero
                    comp_arg = compileExp(arg, cfg)
                    wasm_instr.append(WasmInstrConst("i32", 0))
                    wasm_instr.extend(comp_arg)
                    wasm_instr.append(WasmInstrIntRelOp("i32", "eq"))
                    
        case BinOp(left, op, right):
            left_exp = compileExp(left, cfg)
            right_exp = compileExp(right, cfg)
            wasm_instr.extend(compileBinOp(op, tyOfExp(left), left_exp, right_exp))
        
        case ArrayInitDyn(array_len, elem, elemty):
            if isinstance(elemty, NotVoid) and isinstance(elemty.ty, Array):
                
                wasm_instr.extend(compileInitArray(array_len, elemty.ty.elemTy, cfg))
                wasm_instr.extend(compileDynamicInitArray(array_len, elem))
        
        case ArrayInitStatic(elems, elemty):
            if isinstance(elemty, NotVoid) and isinstance(elemty.ty, Array):
                
                array_length = IntConst(len(elems))
                wasm_instr.extend(compileInitArray(array_length, elemty.ty.elemTy, cfg))
                
                wasm_instr.extend(compileStaticInitArray(elems))
        
                
        case Subscript(array, index):
            wasm_instr.extend(arrayOffsetInstrs(array, index))
            if isinstance(array.ty, Array):
                wasm_instr.extend(compileSubscript(array.ty.elemTy))
            
            
            wasm_instr.append(WasmInstrMem("i32", "load"))
            if isinstance(array.ty, Array) and not isinstance(array.ty.elemTy, Bool):
                wasm_instr.append(WasmInstrConvOp("i64.extend_i32_u"))
            
    return wasm_instr
 

def compileBinOp(op: binaryop, ty: ty, left_exp: list[WasmInstr], right_exp: list[WasmInstr]) -> list[WasmInstr]:
    """
    Function to compile Binary Operator
    """
    result_type = "i64" if isinstance(ty, Int) else "i32"
    instr_list: list[WasmInstr] = []
    instr_list.extend(left_exp)
    match op:
        case Add():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrNumBinOp(result_type, "add"))
        case Sub():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrNumBinOp(result_type, "sub"))
        case Mul():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrNumBinOp(result_type, "mul"))
        case Less():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "lt_s"))
        case Greater():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "gt_s"))
        case LessEq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "le_s"))
        case GreaterEq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "ge_s"))
        case Eq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "eq"))
        case NotEq():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp(result_type, "ne"))
        case And():
            instr_list.append(WasmInstrIf("i32", right_exp, [WasmInstrConst("i32", 0)]))
        case Or():
            instr_list.append(WasmInstrIf("i32", [WasmInstrConst("i32", 1)], right_exp))
            
        case Is():
            instr_list.extend(right_exp)
            instr_list.append(WasmInstrIntRelOp("i32", "eq"))
    return instr_list
        
def tyOfExp(e: exp) -> ty:
    """
    Function to return the type of an expression
    """
    match e.ty:
        case NotVoid():
            return e.ty.ty
        case _:
            raise AttributeError(f"Type of expression {e} should be NotVoid() but is {e.ty}")
        
def compileCall(exp: Call, cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Function to compile a call
    """
    instr: list[WasmInstr] = []
    for arg in exp.args:
                instr.extend(compileExp(arg, cfg))
    if exp.var.name == "print":
        # check if print must be int or bool
        print_type = "i64" if isinstance(tyOfExp(exp.args[0]), Int) else "bool"
        instr.append(WasmInstrCall(WasmId(f"$print_{print_type}")))
    if exp.var.name == "input_int":
        instr.append(WasmInstrCall(WasmId("$input_i64")))
    if exp.var.name == "len":
        instr.extend(arrayLenInstrs())
        
    return instr

def compileLoopBody(cond: exp, body: list[stmt], cfg:CompilerConfig) -> list[WasmInstr]:
    """
    Function to compile loop body
    """
    body_instr: list[WasmInstr] = []
    body_instr.extend(compileExp(cond, cfg))
    body_instr.append(WasmInstrIf(None, [], [WasmInstrBranch(WasmId("$loop_0_exit"), False)]))
    body_instr.extend(compileStmts(body, cfg))
    body_instr.append(WasmInstrBranch(WasmId("$loop_0_start"), False))
    return body_instr

def compileInitArray(lenExp: atomExp, elemTy: ty, cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Generates code to initialize an array without initializing the elements
    """
    
    wasm_instr: list[WasmInstr] = []
    
    if isinstance(lenExp, IntConst):
        wasm_instr.extend([WasmInstrConst("i64", lenExp.value),
                           WasmInstrVarLocal("set", Locals.tmp_i64)])
    
    if isinstance(lenExp, Name):
        wasm_instr.extend([WasmInstrVarLocal("get", WasmId(f"${lenExp.var.name}")),
                           WasmInstrVarLocal("set", Locals.tmp_i64)])
        
    wasm_trap = WasmInstrTrap()
    length_error: list[WasmInstr] = Errors.outputError(Errors.arraySize)
    length_error.append(wasm_trap)
    
    
    
    
    # Check if array size is greater than 0
    wasm_instr.extend([WasmInstrConst("i64", 0),
                        WasmInstrVarLocal("get", Locals.tmp_i64),
                        WasmInstrIntRelOp("i64", "gt_s"),
                        WasmInstrIf(None, length_error, [])
                        ])
    
    max_num_elems = cfg.maxArraySize // 8
    
    # Check if array size is less than the maximum allowed size
    wasm_instr.extend([WasmInstrConst("i64", max_num_elems),
                        WasmInstrVarLocal("get", Locals.tmp_i64),
                        WasmInstrIntRelOp("i64", "lt_s"),
                        WasmInstrIf(None, length_error, [])])
    
    # Construct header
    wasm_instr.extend([WasmInstrVarGlobal("get", Globals.freePtr),
                        WasmInstrVarLocal("get", Locals.tmp_i64), 
                        WasmInstrConvOp("i32.wrap_i64"),
                        WasmInstrConst("i32", 4),
                        WasmInstrNumBinOp("i32", "shl"),
                        WasmInstrConst("i32", 3 if isinstance(elemTy, Array) else 1),
                        WasmInstrNumBinOp("i32","xor"),
                        WasmInstrMem("i32", "store")
                        ])
    
    wasm_instr.extend([WasmInstrVarGlobal("get", Globals.freePtr),
                        WasmInstrVarLocal("get", Locals.tmp_i64), 
                        WasmInstrConvOp("i32.wrap_i64"),
                        WasmInstrConst("i32", 8 if isinstance(elemTy, Int) else 4),
                        WasmInstrNumBinOp("i32", "mul"),
                        WasmInstrConst("i32", 4),
                        WasmInstrNumBinOp("i32","add"),
                        WasmInstrVarGlobal("get", Globals.freePtr),
                        WasmInstrNumBinOp("i32","add"),
                        WasmInstrVarGlobal("set", Globals.freePtr)
                        ])
        
    return wasm_instr

def compileStaticInitArray(elems: list[atomExp]) -> list[WasmInstr]:
    
    wasm_instr: list[WasmInstr] = []
    for i, elem in enumerate(elems):
        if isinstance(elem, IntConst) or isinstance(elem, BoolConst):
            wasm_instr.extend([WasmInstrVarLocal("tee", Locals.tmp_i32),
                            WasmInstrVarLocal("get", Locals.tmp_i32),
                            WasmInstrConst("i32", 4 if i == 0 else ((i)*(8 if isinstance(elem, IntConst) else 4))+4),
                            WasmInstrNumBinOp("i32", "add"),
                            WasmInstrConst("i64" if isinstance(elem, IntConst) else "i32", int(elem.value)),
                            WasmInstrMem("i64" if isinstance(elem, IntConst) else "i32", "store")
                            ])
        if isinstance(elem, Name):
            wasm_instr.extend([WasmInstrVarLocal("tee", Locals.tmp_i32),
                            WasmInstrVarLocal("get", Locals.tmp_i32),
                            WasmInstrConst("i32", 4 if i == 0 else ((i)*4)+4),
                            WasmInstrNumBinOp("i32", "add"),
                            WasmInstrVarLocal("get", WasmId(f"${elem.var.name}")),
                            WasmInstrMem("i64" if isinstance(elem.ty, Int) else "i32", "store")])  
    return wasm_instr

def compileDynamicInitArray(array_len: atomExp, elem: atomExp) -> list[WasmInstr]:
    
    wasm_instr: list[WasmInstr] = []
    
    wasm_instr.extend([WasmInstrVarLocal("tee", Locals.tmp_i32),
                            WasmInstrVarLocal("get", Locals.tmp_i32),
                            WasmInstrConst("i32", 4),
                            WasmInstrNumBinOp("i32", "add"),
                            WasmInstrVarLocal("set", Locals.tmp_i32)])
    
    loop_body: list[WasmInstr] = [WasmInstrVarLocal("get", Locals.tmp_i32),
                             WasmInstrVarGlobal("get", Globals.freePtr),
                             WasmInstrIntRelOp("i32","lt_u"),
                             WasmInstrIf(None, [], [WasmInstrBranch(WasmId("$loop_exit"), False)]),
                             WasmInstrVarLocal("get", Locals.tmp_i32),
                             WasmInstrConst("i64" if isinstance(elem, IntConst) else "i32", elem.value) if isinstance(elem, (IntConst, BoolConst)) 
                             else WasmInstrVarLocal("get", WasmId(f"${elem.var.name}")),
                             WasmInstrMem("i64" if isinstance(elem, (IntConst)) or isinstance(elem.ty, (Int, Bool)) else "i32","store"),
                             WasmInstrVarLocal("get", Locals.tmp_i32),
                             WasmInstrConst("i32", 8 if isinstance(elem, IntConst) else 4), # TODO: might need to check this for variables
                             WasmInstrNumBinOp("i32", "add"),
                             WasmInstrVarLocal("set", Locals.tmp_i32),
                             WasmInstrBranch(WasmId("$loop_start"), False)]
    
    
    loop: list[WasmInstr] = [WasmInstrLoop(WasmId("$loop_start"), loop_body)]
    wasm_instr.append(WasmInstrBlock(WasmId("$loop_exit"), None, loop))              
            
    return wasm_instr

def arrayLenInstrs() -> list[WasmInstr]:
    """
    Generates code that expects the array address on top of stack and puts the length on top of stack
    """
    wasm_instr: list[WasmInstr] = []
    
    wasm_instr.extend([WasmInstrMem("i32", "load"),
                       WasmInstrConst("i32", 4),
                       WasmInstrNumBinOp("i32", "shr_u"),
                       WasmInstrConvOp("i64.extend_i32_u")
                       ])
    
    return wasm_instr

def arrayOffsetInstrs(arrayExp: atomExp, indexExp: atomExp) -> list[WasmInstr]:
    """
    Returns instructions that places the memory offset for a certain array element on top of stack
    """
    
    wasm_instr: list[WasmInstr] = []
    
    wasm_trap = WasmInstrTrap()
    index_error: list[WasmInstr] = Errors.outputError(Errors.arrayIndexOutOfBounds)
    index_error.append(wasm_trap)
    
    if isinstance(indexExp, IntConst):
        wasm_instr.append(WasmInstrConst("i64", indexExp.value))
    elif isinstance(indexExp, Name):
        wasm_instr.append(WasmInstrVarLocal("get", WasmId(f"${indexExp.var.name}")))
    
    
    wasm_instr.extend([WasmInstrConst("i64", 0), 
                       WasmInstrIntRelOp("i64", "lt_s"),
                       WasmInstrIf(None, index_error, [])])

    if (isinstance(arrayExp, Name)):
        wasm_instr.extend([WasmInstrVarLocal("get", WasmId(f"${arrayExp.var.name}"))])
        
        wasm_instr.extend(arrayLenInstrs())
        if isinstance(indexExp, IntConst):
            wasm_instr.extend([WasmInstrConst("i64", indexExp.value + 1),
                            WasmInstrIntRelOp("i64", "lt_s"),
                            WasmInstrIf(None,  index_error, [])
                            ])
            
            wasm_instr.extend([WasmInstrVarLocal("get", WasmId(f"${arrayExp.var.name}")),
                                WasmInstrConst("i64", indexExp.value)
                                ])
        elif isinstance(indexExp, Name):
            wasm_instr.extend([WasmInstrVarLocal("get", WasmId(f"${indexExp.var.name}")),
                               WasmInstrConst("i64", 1),
                               WasmInstrNumBinOp("i64", "add"),
                               WasmInstrIntRelOp("i64", "lt_s"),
                               WasmInstrIf(None,  index_error, [])
                               ])
            
            wasm_instr.extend([WasmInstrVarLocal("get", WasmId(f"${arrayExp.var.name}")),
                               WasmInstrVarLocal("get", WasmId(f"${indexExp.var.name}"))
                               ])
        
    return wasm_instr

def compileSubscript(array_elem_ty: ty) -> list[WasmInstr]:
    wasm_instr: list[WasmInstr] = []
    wasm_instr.extend([WasmInstrConvOp("i32.wrap_i64"),
                       WasmInstrConst("i32", 8 if isinstance(array_elem_ty, Int) else 4),
                       WasmInstrNumBinOp("i32", "mul"),
                       WasmInstrConst("i32", 4),
                       WasmInstrNumBinOp("i32","add"),
                       WasmInstrNumBinOp("i32","add")
                       ])
    
    return wasm_instr