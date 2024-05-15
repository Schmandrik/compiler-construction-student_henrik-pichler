from parsers.common import *

type Json = str | int | dict[str, Json]

def ruleJson(toks: TokenStream) -> Json:
    """
    Parses a JSON object, a JSON string, or a JSON number.
    """
    if toks.lookahead().type == "STRING":
        return toks.next().strip('"')
    if toks.lookahead().type == "INT":
        return int(toks.next().value)
    if toks.lookahead().type == "LBRACE":
        toks.next()
        return ruleEntryList(toks)
    unexpectedToken(toks.next(), "STRING, INT or LBRACE")

def ruleEntryList(toks: TokenStream) -> dict[str, Json]:
    """
    Parses the content of a JSON object.
    """
    result: dict[str, Json] = {}
    while toks.lookahead().type != "RBRACE":
        if toks.lookahead().type != "COMMA":
            if toks.lookahead().type != "STRING":
                unexpectedToken(toks.next(), "STRING")
            string_token = toks.next().strip('"')
            
            if toks.lookahead().type != "COLON":
                unexpectedToken(toks.next(), "COLON")
            
            toks.next()
            entry_json_token = ruleJson(toks)
            
            result[string_token] = entry_json_token
        else:
            toks.next()
    toks.next()
    return result

def parse(code: str) -> Json:
    parser = mkLexer("./src/parsers/tinyJson/tinyJson_grammar.lark")
    tokens = list(parser.lex(code))
    log.info(f'Tokens: {tokens}')
    toks = TokenStream(tokens)
    res = ruleJson(toks)
    toks.ensureEof(code)
    return res
