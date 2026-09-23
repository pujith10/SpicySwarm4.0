import ast
import math
import sys
import time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
import re

class WebSearchInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=250, description="The search term")
    max_results: int = Field(default=5, ge=1, le=10)
    domain_filter: Optional[str] = Field(default=None, max_length=100)

    @field_validator('query')
    def validate_safe_query(cls, v):
        # Reject terminal control characters or dangerous injection markers
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', v):
            raise ValueError("Query contains forbidden control characters")
        return v.strip()


class PythonSandboxInput(BaseModel):
    code: str = Field(..., min_length=1, max_length=3000, description="Executable Python code")
    timeout_seconds: int = Field(default=5, ge=1, le=10)

    @field_validator('code')
    def validate_ast(cls, code_str: str):
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")

        # AST Inspection: Block dangerous modules and calls
        forbidden_modules = {
            "os", "sys", "subprocess", "socket", "requests", "httpx", "urllib",
            "shutil", "pathlib", "pickle", "importlib", "pty", "builtins"
        }
        forbidden_calls = {
            "eval", "exec", "open", "__import__", "compile", "breakpoint",
            "input", "globals", "locals", "vars", "getattr", "setattr", "delattr"
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in forbidden_modules:
                            raise ValueError(f"Security Policy: Forbidden import '{alias.name}' in sandbox code.")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in forbidden_modules:
                        raise ValueError(f"Security Policy: Forbidden import from '{node.module}' in sandbox code.")
            
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    raise ValueError(f"Security Policy: Call to forbidden function '{node.func.id}()'")
                elif isinstance(node.func, ast.Attribute) and node.func.attr in ("__subclasses__", "__bases__", "__class__"):
                    raise ValueError("Security Policy: Introspection exploit attempt blocked.")

        return code_str


class KnowledgeQueryInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    top_k: int = Field(default=5, ge=1, le=20)


class SafePythonSandbox:
    """
    Sandboxed AST execution runner for computational tasks (math, data analysis).
    Runs with restricted builtins and an AST-verified syntax tree.
    """
    SAFE_BUILTINS = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sum': sum, 'len': len, 'range': range, 'enumerate': enumerate,
        'zip': zip, 'map': map, 'filter': filter, 'int': int,
        'float': float, 'str': str, 'bool': bool, 'list': list,
        'dict': dict, 'set': set, 'tuple': tuple, 'math': math
    }

    @classmethod
    def execute(cls, code: str) -> Dict[str, Any]:
        try:
            # Validate AST first
            validated_code = PythonSandboxInput.validate_ast(code)
            
            # Prepare clean scope
            safe_globals = {"__builtins__": cls.SAFE_BUILTINS, "math": math}
            safe_locals: Dict[str, Any] = {}
            
            # Capture output if print or variable assignment
            output_collector = []
            safe_globals["print"] = lambda *args: output_collector.append(" ".join(str(a) for a in args))
            
            # Execute with AST safety
            compiled = compile(validated_code, "<sandboxed_eval>", "exec")
            exec(compiled, safe_globals, safe_locals)
            
            # Look for explicit result or printed output
            if output_collector:
                result_str = "\n".join(output_collector)
            elif "result" in safe_locals:
                result_str = str(safe_locals["result"])
            elif safe_locals:
                # Get the last assigned variable
                last_var = list(safe_locals.values())[-1]
                result_str = str(last_var)
            else:
                result_str = "Execution finished with no output"
                
            return {"success": True, "output": result_str, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": f"Sandbox Error: {str(e)}"}
