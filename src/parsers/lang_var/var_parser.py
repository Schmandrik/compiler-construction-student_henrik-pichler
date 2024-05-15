from lark import ParseTree
from parsers.common import *
from lang_var.var_ast import mod, stmt, Assign, StmtExp, Ident, Module, Call, exp, Name, Sub, Add, Mul, BinOp, IntConst, USub, UnOp
from lark.tree import Tree

grammarFile = "./src/parsers/lang_var/var_grammar.lark"

def parseModule(args: ParserArgs) -> mod:
    parseTree = parseAsTree(args, grammarFile, 'lvar')
    ast = parseTreeToModuleAst(parseTree)
    log.debug(f'AST: {ast}')
    return ast


def parseTreeToModuleAst(t: ParseTree) -> mod:
    
    module_list = parseTreeToStmtListAst(t)
    
    return Module(module_list)

def parseTreeToStmtListAst(t: ParseTree) -> list[stmt]:
    stmt_list : list[stmt] = []
    for child in t.children:
        if isinstance(child, Tree):
            child = asTree(child)
            stmt_list.append(parseTreeToStmtAst(child))
    return stmt_list

def parseTreeToStmtAst(t: ParseTree) -> stmt:
    match t.data:
        case "assign_exp":
            assign_var = Ident(str(t.children[0]))
            childs = asTree(t.children[1])
            exps = parseTreeToExpAst(childs)
            return Assign(assign_var,exps)
            
        case "exp":
            exp = asTree(t.children[0])
            return StmtExp(parseTreeToExpAst(exp))

        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for stmt: {t}')

def parseTreeToExpAst(t: ParseTree) -> exp:
    match t.data:
        case "int_exp":
            return IntConst(int(asToken(t.children[0])))

        case "add_exp":
            exps = [asTree(child) for child in t.children]
            exp1: exp = parseTreeToExpAst(exps[0])
            exp2: exp = parseTreeToExpAst(exps[1])
            op = BinOp(exp1, Add(), exp2)
            return op
        
        case "sub_exp":
            exps = [asTree(child) for child in t.children]
            exp1: exp = parseTreeToExpAst(exps[0])
            exp2: exp = parseTreeToExpAst(exps[1])
            op = BinOp(exp1, Sub(), exp2)
            return op

        case "mul_exp":
            exps = [asTree(child) for child in t.children]
            exp1: exp = parseTreeToExpAst(exps[0])
            exp2: exp = parseTreeToExpAst(exps[1])
            op = BinOp(exp1, Mul(), exp2)
            return op
        
        case "neg_exp":
            childs = asTree(t.children[0])
            op = UnOp(USub(), parseTreeToExpAst(childs))
            return op
        
        case "exp_1" | "exp_2":
            return parseTreeToExpAst(asTree(t.children[0]))
        
        case "paren_exp":
            if isinstance(t.children[0], Tree):
                if asTree(t.children[0]).data == "paren_exp":
                    return parseTreeToExpAst(asTree(t.children[0]))
            
            return parseTreeToExpAst(asTree(t.children[1]))
        
        case "assign_name":
            assign_name = Ident(str(asToken(t.children[0])))
            return Name(assign_name)
        
        case "func_call_exp":
            childs: ParseTree = asTree(t.children[0])
            call_type = Ident(str(asToken(childs.children[0])))
            call_exp: list[exp] = []
            
            childs = asTree(childs.children[1])
            print_content = childs.children
            if len(print_content) == 2:
                pass
            else:
                print_args: list[Token | ParseTree] = print_content[1:-1]
                call_exp = [parseTreeToExpAst(asTree(child)) for child in print_args]

            return Call(call_type, call_exp)
        
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for exp: {t}')
        

