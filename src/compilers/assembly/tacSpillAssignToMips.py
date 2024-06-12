import assembly.tacSpill_ast as tacSpill
import assembly.mips_ast as mips
from typing import *
from assembly.common import *
from assembly.mipsHelper import *
from common.compilerSupport import *

def assignToMips(i: tacSpill.Assign) -> list[mips.instr]:
    """
    creates MIPS instructions for assign statement
    """
    var = i.var
    
    # match what should be assigned
    match i.left:
        case tacSpill.Prim(p):
            match p:
                case tacSpill.Const(v):
                    # load constant into register
                    return [mips.LoadI(reg(var), imm(v))]
                case tacSpill.Name(v):
                    # move variable from one register to another
                    return [mips.Move(reg(var), reg(v))]
                
        case tacSpill.BinOp(left, op, right):
            # What operation is used for the binop
            op_name = getTacSpillOp(op)
            
            # Case: BinOp(var, op, var)
            if isinstance(left, tacSpill.Name) and isinstance(right, tacSpill.Name):
                return [mips.Op(op_name[0], reg(var), reg(left.var), reg(right.var))]
            
            # Case: BinOp(var, op, const)
            elif isinstance(left, tacSpill.Name) and isinstance(right, tacSpill.Const):
                
                # Operation can be an immediate operation
                if isinstance(op_name[1], (mips.AddI, mips.LessI)):
                    op_nameI: mips.opI = op_name[1]
                    opI: mips.instr = mips.OpI(op_nameI, reg(var), reg(left.var), imm(right.value))
                    return [opI]
                
                # Operation cannot be immediate
                else:
                    operator: mips.op = op_name[0]
                    load_op = mips.LoadI(reg(tacSpill.Ident("$t2")), imm(right.value))
                    opI: mips.instr = mips.Op(operator, reg(var), reg(left.var), reg(tacSpill.Ident("$t2")))
                    return [load_op, opI]
            
            # Case: BinOp(const, op, var)
            elif isinstance(left, tacSpill.Const) and isinstance(right, tacSpill.Name):
                
                # Operation can be immediate
                if isinstance(op_name[1], (mips.AddI, mips.LessI)):
                    op_nameI: mips.opI = op_name[1]
                    opI: mips.instr = mips.OpI(op_nameI, reg(var), reg(right.var), imm(left.value))
                    return [opI]
                
                # Operation cannot be immediate
                else:
                    operator: mips.op = op_name[0]
                    load_op = mips.LoadI(reg(tacSpill.Ident("$t2")), imm(left.value))
                    opI: mips.instr = mips.Op(operator, reg(var), reg(tacSpill.Ident("$t2")), reg(right.var))
                    return [load_op, opI]
            
            # Case: BinOp(const, var, const)
            elif isinstance(left, tacSpill.Const) and isinstance(right, tacSpill.Const):
                res_const: int = constantFolding(op_name[0], left.value, right.value)
                opI: mips.instr = mips.LoadI(reg(var), imm(res_const))
                return [opI]
            
            else:
                return []
            
def getTacSpillOp(op: tacSpill.op) -> tuple[mips.op, (mips.opI|None)]:
    """
    Get MIPS operation from TacSpill operation
    """
    
    match op.name:
        case "ADD":
            # Add might also be done as an immediate operation
            mips_op_name = (mips.Add(), mips.AddI())
        case "SUB":
            mips_op_name = (mips.Sub(), None)
        case "MUL":
            mips_op_name = (mips.Mul(), None)
        case "EQ":
            mips_op_name = (mips.Eq(), None)
        case "NE":
            mips_op_name = (mips.NotEq(), None)
        case "LT_S":
            # Less than might also be done as an immediate operation
            mips_op_name = (mips.Less(), mips.LessI())
        case "LE_S":
            mips_op_name = (mips.LessEq(), None)
        case "GE_S":
            mips_op_name = (mips.GreaterEq(), None)
        case "GT_S":
            mips_op_name = (mips.Greater(), None)
        case _:
            raise ValueError(f"Operator {op.name} not supported")
        
    return mips_op_name

def constantFolding(op: mips.op, left: int, right: int) -> int:
    """
    Compute 2 values together at compile time
    """
    match op:
        case mips.Add():
            return left + right
        case mips.Sub():
            return left - right
        case mips.Mul():
            return left * right
        case _:
            raise ValueError(f"Operator {op} not supported")