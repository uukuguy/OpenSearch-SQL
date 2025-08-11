"""
LLM model integration for OpenSearch-SQL pipeline.
"""
import os
import requests
import time
import json
import re
from ..utils.loguru_config import get_logger
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Union
from ..core import Logger


logger = get_logger(__name__)
class LLMModelBase(ABC):
    """
    Abstract base class for LLM models.
    """
    
    def __init__(self, step: str, model: str):
        """
        Initialize the LLM model.
        
        Args:
            step (str): Current pipeline step.
            model (str): Model identifier.
        """
        self.step = step
        self.model = model
        self.cost = 0.0
        
    @abstractmethod
    def get_ans(self, messages: str, temperature: float = 0.0, top_p: Optional[float] = None, 
                n: int = 1, single: bool = True, **kwargs) -> Union[str, List[str]]:
        """
        Get response from the model.
        
        Args:
            messages (str): Input messages/prompt.
            temperature (float): Sampling temperature.
            top_p (Optional[float]): Top-p sampling parameter.
            n (int): Number of responses to generate.
            single (bool): Whether to return single response or list.
            **kwargs: Additional model parameters.
            
        Returns:
            Union[str, List[str]]: Model response(s).
        """
        pass
    
    def log_record(self, prompt_text: str, output: str):
        """
        Log the conversation.
        
        Args:
            prompt_text (str): Input prompt.
            output (str): Model output.
        """
        try:
            logger = Logger()
            logger.log_conversation(prompt_text, "Human", self.step)
            logger.log_conversation(output, "AI", self.step)
        except Exception as e:
            logger.warning(f"Failed to log conversation: {e}")
    
    def fewshot_parse(self, question: str, evidence: str, sql: str) -> str:
        """
        Parse few-shot examples.
        
        Args:
            question (str): Question text.
            evidence (str): Evidence text.
            sql (str): SQL query.
            
        Returns:
            str: Parsed few-shot example.
        """
        from .prompts import PromptManager
        prompt_manager = PromptManager()
        
        s = prompt_manager.get_prompt("parse_fewshot").format(question=question, sql=sql)
        ext = self.get_ans(s)
        ext = ext.replace('```', '').strip()
        ext = ext.split("#SQL:")[0]  # Prevent format issues
        ans = self.convert_table(ext, sql)
        return ans
    
    def convert_table(self, s: str, sql: str) -> str:
        """
        Convert table aliases in the parsed output.
        
        Args:
            s (str): Parsed string.
            sql (str): Original SQL.
            
        Returns:
            str: Converted string.
        """
        l = re.findall(r' ([^ ]*) +AS +([^ ]*)', sql)
        x, v = s.split("#values:")
        t, s_part = x.split("#SELECT:")
        for li in l:
            s_part = s_part.replace(f"{li[1]}.", f"{li[0]}.")
        return t + "#SELECT:" + s_part + "#values:" + v


def request_api(url: str, model: str, messages: str, temperature: float, 
               top_p: float, n: int, key: str, **kwargs) -> Dict[str, Any]:
    """
    Make API request to LLM service.
    
    Args:
        url (str): API endpoint URL.
        model (str): Model name.
        messages (str): Input messages.
        temperature (float): Sampling temperature.
        top_p (float): Top-p sampling.
        n (int): Number of responses.
        key (str): API key.
        **kwargs: Additional parameters.
        
    Returns:
        Dict[str, Any]: API response.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    
    json_data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an SQL expert, skilled in handling various SQL-related issues."
            },
            {
                "role": "user", 
                "content": messages
            }
        ],
        "max_tokens": 800,
        "temperature": temperature,
        "top_p": top_p,
        "n": n,
        **kwargs
    }
    
    response = requests.post(url=url, json=json_data, headers=headers)
    return response.json()


class GPTModel(LLMModelBase):
    """
    OpenAI GPT model implementation.
    """
    
    def __init__(self, step: str, model: str = "gpt-4o"):
        super().__init__(step, model)
        
    def get_ans(self, messages: str, temperature: float = 0.0, top_p: Optional[float] = None,
                n: int = 1, single: bool = True, **kwargs) -> Union[str, List[str]]:
        """
        Get response from GPT model.
        """
        url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"
        key = os.getenv("OPENAI_API_KEY")
        
        if not key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
            
        if top_p is None:
            top_p = 1.0
            
        count = 0
        max_retries = 5
        
        while count < max_retries:
            try:
                res = request_api(url, self.model, messages, temperature, top_p, n, key, **kwargs)
                
                if 'error' in res:
                    logger.error(f"OpenAI API error: {res['error']}")
                    if count == max_retries - 1:
                        raise Exception(f"OpenAI API error: {res['error']}")
                    time.sleep(2 ** count)
                    count += 1
                    continue
                
                choices = res.get('choices', [])
                if not choices:
                    raise Exception("No choices in response")
                    
                if single or n == 1:
                    result = choices[0]['message']['content']
                    self.log_record(messages, result)
                    return result
                else:
                    results = [choice['message']['content'] for choice in choices]
                    self.log_record(messages, str(results))
                    return results
                    
            except Exception as e:
                logger.error(f"Error in GPT request (attempt {count + 1}): {e}")
                count += 1
                if count >= max_retries:
                    raise
                time.sleep(2 ** count)
        
        raise Exception(f"Failed to get response after {max_retries} attempts")


class ClaudeModel(LLMModelBase):
    """
    Anthropic Claude model implementation.
    """
    
    def __init__(self, step: str, model: str = "claude-3-opus"):
        super().__init__(step, model)
        
    def get_ans(self, messages: str, temperature: float = 0.0, top_p: Optional[float] = None,
                n: int = 1, single: bool = True, **kwargs) -> Union[str, List[str]]:
        """
        Get response from Claude model.
        """
        # For now, use OpenAI-compatible API format
        # This would need to be updated for actual Claude API
        url = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1") + "/messages"
        key = os.getenv("CLAUDE_API_KEY")
        
        if not key:
            raise ValueError("CLAUDE_API_KEY environment variable not set")
        
        # Claude has different API format, but for simplicity using OpenAI format
        # In production, this should use Claude's actual API format
        return self._fallback_openai_format(messages, temperature, top_p, n, single, **kwargs)
    
    def _fallback_openai_format(self, messages: str, temperature: float, top_p: Optional[float],
                                n: int, single: bool, **kwargs) -> Union[str, List[str]]:
        """Fallback to OpenAI format for now."""
        # This is a placeholder - in production use actual Claude API
        logger.warning("Using OpenAI API format for Claude - update for production")
        gpt_model = GPTModel(self.step, "gpt-4o")
        return gpt_model.get_ans(messages, temperature, top_p, n, single, **kwargs)


class MockModel(LLMModelBase):
    """
    Mock model for testing purposes.
    """
    
    def __init__(self, step: str, model: str = "mock"):
        super().__init__(step, model)
        
    def get_ans(self, messages: str, temperature: float = 0.0, top_p: Optional[float] = None,
                n: int = 1, single: bool = True, **kwargs) -> Union[str, List[str]]:
        """
        Get mock response.
        """
        # Generate a simple mock SQL response
        mock_response = "SELECT * FROM table WHERE condition = 'value';"
        
        if single or n == 1:
            self.log_record(messages, mock_response)
            return mock_response
        else:
            mock_responses = [f"{mock_response} -- Response {i+1}" for i in range(n)]
            self.log_record(messages, str(mock_responses))
            return mock_responses


def model_chose(step: str, model: str = "gpt-4o") -> LLMModelBase:
    """
    Choose and instantiate the appropriate model.
    
    Args:
        step (str): Current pipeline step.
        model (str): Model identifier.
        
    Returns:
        LLMModelBase: Model instance.
    """
    model_lower = model.lower()
    
    if model_lower.startswith("gpt") or "openai" in model_lower:
        return GPTModel(step, model)
    elif model_lower.startswith("claude") or "anthropic" in model_lower:
        return ClaudeModel(step, model)
    elif model_lower == "mock" or "test" in model_lower:
        return MockModel(step, model)
    else:
        # Default to GPT
        logger.warning(f"Unknown model {model}, defaulting to GPT-4o")
        return GPTModel(step, "gpt-4o")


def get_sql_from_response(response: str, return_question: bool = False, 
                         n: int = 1, single: bool = True) -> Tuple[Union[str, List[str]], Optional[str]]:
    """
    Extract SQL from model response.
    
    Args:
        response (str): Model response.
        return_question (bool): Whether to return question analysis.
        n (int): Number of expected SQLs.
        single (bool): Whether single response expected.
        
    Returns:
        Tuple[Union[str, List[str]], Optional[str]]: Extracted SQL(s) and optional question analysis.
    """
    if not response:
        return ("" if single else [], None)
    
    # Extract SQL from response
    sql_pattern = r'```sql\s*(.*?)\s*```'
    sql_matches = re.findall(sql_pattern, response, re.DOTALL | re.IGNORECASE)
    
    if not sql_matches:
        # Look for SELECT statements
        select_pattern = r'(SELECT\s+.*?;?)'
        select_matches = re.findall(select_pattern, response, re.DOTALL | re.IGNORECASE)
        if select_matches:
            sql_matches = select_matches
    
    if not sql_matches:
        # Return the response as-is if no SQL pattern found
        sql_matches = [response.strip()]
    
    # Clean up SQL
    cleaned_sqls = []
    for sql in sql_matches:
        cleaned_sql = sql.strip()
        if cleaned_sql.endswith(';'):
            cleaned_sql = cleaned_sql[:-1]
        cleaned_sqls.append(cleaned_sql)
    
    # Extract question analysis if requested
    question_analysis = None
    if return_question:
        # Look for question analysis in response
        question_pattern = r'Question Analysis:?\s*(.*?)(?=SQL|$)'
        question_match = re.search(question_pattern, response, re.DOTALL | re.IGNORECASE)
        if question_match:
            question_analysis = question_match.group(1).strip()
    
    # Return based on requirements
    if single:
        return (cleaned_sqls[0] if cleaned_sqls else "", question_analysis)
    else:
        # Return up to n SQLs
        return (cleaned_sqls[:n], question_analysis)


class ModelFactory:
    """
    Factory class for creating LLM model instances.
    """
    
    @staticmethod
    def create_model(engine: str, step: str = "default") -> LLMModelBase:
        """
        Create a model instance based on the engine type.
        
        Args:
            engine (str): Engine/model type.
            step (str): Pipeline step name.
            
        Returns:
            LLMModelBase: Model instance.
        """
        model = model_chose(step, engine)
        # Add get_response method as alias for get_ans for compatibility
        if not hasattr(model, 'get_response'):
            model.get_response = model.get_ans
        return model
    
    @staticmethod
    def get_available_models() -> List[str]:
        """
        Get list of available model types.
        
        Returns:
            List[str]: Available model identifiers.
        """
        return ["gpt-4o", "gpt-3.5-turbo", "claude-3-opus", "mock"]