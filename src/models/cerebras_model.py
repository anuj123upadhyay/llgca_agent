



import os
from typing import List, TypeVar, Optional
from portia import GenerativeModel, Message, LLMProvider
from pydantic import BaseModel
import requests

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)

class CerebrasModel(GenerativeModel):
    provider: LLMProvider = LLMProvider.CUSTOM
    
    def __init__(self):
        # Get API key
        self.api_key = os.environ.get("CEREBRAS_API_KEY")
        if not self.api_key:
            raise ValueError("CEREBRAS_API_KEY not found in environment")
            
        # Set up direct API access instead of using the problematic SDK
        self.base_url = "https://api.cerebras.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.model_name = "llama-4-scout-17b-16e-instruct"
        
    def get_response(self, messages: List[Message]) -> Message:
        """Get response from Cerebras API using direct API calls"""
        try:
            # Format messages for Cerebras
            formatted_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            # Call Cerebras API directly
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model_name,
                    "messages": formatted_messages,
                    "max_tokens": 2048,
                    "temperature": 0.2,
                    "stream": False
                }
            )
            response.raise_for_status()
            
            # Return the response
            content = response.json()["choices"][0]["message"]["content"]
            return Message(
                content=content,
                role="assistant"
            )
        except Exception as e:
            raise Exception(f"Cerebras API error: {str(e)}")

    async def aget_response(self, messages: List[Message]) -> Message:
        """Async version - for now just uses the sync version"""
        return self.get_response(messages)
    
    def get_structured_response(
        self,
        messages: List[Message],
        schema: type[BaseModelT],
    ) -> BaseModelT:
        """Get structured response according to schema"""
        import json
        import re
        
        # Add a system message to prompt for structured output
        schema_json = schema.schema_json()
        system_message = Message(
            role="system",
            content=f"Respond with ONLY a valid JSON object that matches this schema: {schema_json}. Do not include any markdown formatting, code blocks, or explanatory text. Just return the raw JSON."
        )
        
        # Prepend system message
        all_messages = [system_message] + messages
        
        # Get response
        response = self.get_response(all_messages)
        
        # Extract JSON from response content (handle markdown code blocks)
        content = response.content.strip()
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # If no code blocks, try to find JSON directly
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content
        
        # Parse as JSON into schema
        try:
            # First validate it's proper JSON
            json.loads(json_str)
            return schema.parse_raw(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {json_str[:200]}... Error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse response into {schema.__name__}: {str(e)}")

    async def aget_structured_response(
        self,
        messages: List[Message],
        schema: type[BaseModelT],
    ) -> BaseModelT:
        """Async version of get_structured_response"""
        return self.get_structured_response(messages, schema)
    
    def to_langchain(self):
        """Convert to LangChain compatible format"""
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        
        class CerebrasLangChain(BaseChatModel):
            def __init__(self, cerebras_model):
                self.cerebras_model = cerebras_model
                
            def _generate(self, messages, **kwargs):
                # Convert LangChain messages to Portia messages
                portia_messages = []
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        portia_messages.append(Message(role="user", content=msg.content))
                    elif isinstance(msg, SystemMessage):
                        portia_messages.append(Message(role="system", content=msg.content))
                    elif isinstance(msg, AIMessage):
                        portia_messages.append(Message(role="assistant", content=msg.content))
                
                # Get response from Cerebras
                response = self.cerebras_model.get_response(portia_messages)
                
                # Convert to LangChain format
                generation = ChatGeneration(
                    message=AIMessage(content=response.content),
                )
                return ChatResult(generations=[generation])
                
            async def _agenerate(self, messages, **kwargs):
                # For simplicity, just call the sync version
                return self._generate(messages, **kwargs)
                
        return CerebrasLangChain(self)