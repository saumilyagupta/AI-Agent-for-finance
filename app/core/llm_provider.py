"""LLM provider abstraction with Google Gemini and OpenAI support."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import google.generativeai as genai
from langchain_openai import ChatOpenAI
from openai import OpenAI

from app.utils.config import settings
from app.utils.logger import logger


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate text completion."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text completion."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass

    @abstractmethod
    def estimate_cost(self, tokens: int) -> float:
        """Estimate cost in USD."""
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate with tool/function calling support.
        
        Args:
            messages: Conversation history in format [{"role": "user/assistant", "content": "..."}]
            tools: List of tool definitions
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            
        Returns:
            Dict with 'content' (text response), 'tool_calls' (list of tool calls),
            'tokens_used', 'cost', 'model'
        """
        pass


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini LLM provider using native SDK."""

    def __init__(self, model: str = "gemini-1.5-flash"):
        self.model_name = model
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        genai.configure(api_key=settings.google_api_key)
        
        # Use native Google Generative AI SDK for better compatibility
        # Normalize model name - handle various formats
        normalized_model = model.replace("-latest", "").replace("-exp", "")
        
        # Map common model names to their API format
        model_mapping = {
            "gemini-2.0-flash": "gemini-2.0-flash-exp",  # Try experimental first
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-pro": "gemini-pro",
        }
        
        # Try mapped name first, then normalized, then original
        models_to_try = []
        if normalized_model in model_mapping:
            models_to_try.append(model_mapping[normalized_model])
        models_to_try.append(normalized_model)
        if model != normalized_model:
            models_to_try.append(model)
        models_to_try.append("gemini-pro")  # Final fallback
        
        self.model = None
        for model_to_try in models_to_try:
            try:
                self.model = genai.GenerativeModel(model_to_try)
                self.model_name = model_to_try
                logger.info(f"Successfully initialized Gemini model: {model_to_try}")
                break
            except Exception as e:
                logger.debug(f"Failed to initialize model {model_to_try}: {e}")
                continue
        
        if self.model is None:
            raise ValueError(f"Could not initialize any Gemini model. Tried: {models_to_try}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate completion using native Gemini SDK."""
        try:
            import asyncio
            
            # Combine system prompt and user prompt
            # For Gemini, we prepend system prompt to the user prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            else:
                full_prompt = prompt
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Run async generation
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config,
                )
            )

            # Extract content
            content = response.text if hasattr(response, "text") else str(response)
            
            # Get usage info if available
            if hasattr(response, "usage_metadata"):
                tokens_used = (
                    response.usage_metadata.prompt_token_count + 
                    response.usage_metadata.candidates_token_count
                )
            else:
                # Estimate tokens
                full_text = (system_prompt or "") + "\n\n" + prompt + "\n\n" + content
                tokens_used = self.count_tokens(full_text)
            
            cost = self.estimate_cost(tokens_used)

            return {
                "content": content,
                "tokens_used": tokens_used,
                "cost": cost,
                "model": self.model_name,
            }
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            # Try fallback to gemini-pro if current model fails
            if self.model_name != "gemini-pro":
                logger.info("Attempting fallback to gemini-pro")
                try:
                    fallback_model = genai.GenerativeModel("gemini-pro")
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: fallback_model.generate_content(prompt)
                    )
                    content = response.text if hasattr(response, "text") else str(response)
                    tokens_used = self.count_tokens(prompt + content)
                    return {
                        "content": content,
                        "tokens_used": tokens_used,
                        "cost": self.estimate_cost(tokens_used),
                        "model": "gemini-pro",
                    }
                except Exception as e2:
                    logger.error(f"Gemini fallback also failed: {e2}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming completion using native Gemini SDK."""
        try:
            import asyncio
            
            # Combine system prompt and user prompt for streaming
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            else:
                full_prompt = prompt
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
            )
            
            # Run async streaming generation
            loop = asyncio.get_event_loop()
            response_stream = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config,
                    stream=True,
                )
            )
            
            for chunk in response_stream:
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text
                elif hasattr(chunk, "parts"):
                    for part in chunk.parts:
                        if hasattr(part, "text") and part.text:
                            yield part.text
        except Exception as e:
            logger.error(f"Gemini streaming failed: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """Estimate token count (approximate: 1 token ≈ 4 characters)."""
        return len(text) // 4

    def estimate_cost(self, tokens: int) -> float:
        """Estimate cost (Gemini 1.5 Flash: $0.075/$0.30 per 1M tokens)."""
        # Using input pricing as approximation
        return (tokens / 1_000_000) * 0.075

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate with tool calling support for Gemini.
        
        Note: Gemini function calling is currently disabled due to SDK version incompatibility.
        This method raises NotImplementedError to trigger fallback to OpenAI for tool calls.
        """
        logger.info(f"Gemini generate_with_tools called with {len(tools)} tools")
        logger.warning("Gemini function calling disabled - using OpenAI for tool calls")
        
        # Raise NotImplementedError to trigger automatic fallback to OpenAI provider
        # This is intentional - the LLMProviderManager will catch this and use the fallback
        raise NotImplementedError("Gemini function calling not supported in this version")

    def _convert_tools_to_gemini_format(self, tools: List[Dict[str, Any]]) -> List:
        """
        Convert OpenAI-style tools to Gemini format.
        
        Note: Reserved for future Gemini function calling implementation.
        Currently unused as Gemini function calling is disabled.
        """
        if not tools:
            logger.debug("No tools to convert")
            return []
        
        try:
            # Build function declarations as dictionaries (compatible with all versions)
            gemini_functions = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool.get("function", {})
                    func_name = func.get("name", "unknown")
                    logger.debug(f"Converting tool: {func_name}")
                    
                    # Use dict format instead of FunctionDeclaration class
                    gemini_functions.append({
                        "name": func_name,
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                    })
            
            if gemini_functions:
                logger.info(f"Converted {len(gemini_functions)} functions to Gemini format")
                # Return as list of dicts (compatible format)
                return gemini_functions
            
            logger.warning("No valid functions found in tools")
            return []
        except Exception as e:
            logger.error(f"Error converting tools to Gemini format: {e}", exc_info=True)
            return []

    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, Any]]) -> str:
        """
        Convert messages to Gemini prompt format.
        
        Note: Reserved for future Gemini function calling implementation.
        Currently unused as Gemini function calling is disabled.
        """
        # Convert conversation history to a single prompt for Gemini
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                # Check if assistant made tool calls
                if "tool_calls" in msg and msg["tool_calls"]:
                    # Assistant is calling tools
                    tool_calls_desc = []
                    for tc in msg["tool_calls"]:
                        func_name = tc.get("function", {}).get("name", "unknown")
                        func_args = tc.get("function", {}).get("arguments", "{}")
                        tool_calls_desc.append(f"  - {func_name}({func_args})")
                    parts.append(f"Assistant called tools:\n" + "\n".join(tool_calls_desc))
                elif content:
                    # Regular assistant response
                    parts.append(f"Assistant: {content}")
            elif role == "tool":
                # Tool result
                parts.append(f"Tool Result: {content}")
        
        return "\n\n".join(parts)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model_name = model
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.langchain_client = ChatOpenAI(
            model=model,
            openai_api_key=settings.openai_api_key,
            temperature=0.7,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate completion."""
        try:
            # Use messages format for proper system prompt handling
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = await self.langchain_client.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            # Estimate tokens
            tokens_used = self.count_tokens(prompt + content)
            cost = self.estimate_cost(tokens_used)

            return {
                "content": content,
                "tokens_used": tokens_used,
                "cost": cost,
                "model": self.model_name,
            }
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming completion."""
        try:
            # Use messages format for proper system prompt handling
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            async for chunk in self.langchain_client.astream(messages):
                if hasattr(chunk, "content"):
                    yield chunk.content
                else:
                    yield str(chunk)
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """Estimate token count (approximate: 1 token ≈ 4 characters)."""
        return len(text) // 4

    def estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on model."""
        pricing = {
            "gpt-4": (0.03, 0.06),  # input, output per 1K tokens
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-3.5-turbo": (0.0015, 0.002),
            "gpt-4o-mini": (0.00015, 0.0006),
        }
        input_price, output_price = pricing.get(self.model_name, (0.002, 0.002))
        # Assume 50/50 split
        return (tokens / 1000) * ((input_price + output_price) / 2)

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate with tool calling support for OpenAI."""
        import asyncio
        import json
        
        try:
            logger.debug(f"OpenAI generate_with_tools called with {len(messages)} messages, {len(tools)} tools")
            
            # Build request parameters
            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            # Call OpenAI API (run in executor to not block)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(**params)
            )
            
            # Parse response
            message = response.choices[0].message
            content = message.content or ""
            tool_calls = []
            
            # Extract tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    })
                logger.info(f"OpenAI returned {len(tool_calls)} tool calls")
            
            # Get usage info
            tokens_used = 0
            if hasattr(response, "usage"):
                tokens_used = response.usage.total_tokens
                logger.debug(f"OpenAI tokens used: {tokens_used}")
            else:
                # Estimate
                all_text = " ".join([m.get("content", "") if m.get("content") else "" for m in messages]) + content
                tokens_used = self.count_tokens(all_text)
                logger.debug(f"OpenAI estimated tokens: {tokens_used}")
            
            cost = self.estimate_cost(tokens_used)
            
            result = {
                "content": content,
                "tool_calls": tool_calls,
                "tokens_used": tokens_used,
                "cost": cost,
                "model": self.model_name,
            }
            
            logger.info(f"OpenAI generate_with_tools completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI generate_with_tools failed: {e}", exc_info=True)
            logger.error(f"Messages passed to OpenAI: {json.dumps(messages, indent=2)[:500]}")
            raise


class LLMProviderManager:
    """Manager for LLM providers with fallback support."""

    def __init__(self):
        self.primary_provider: Optional[LLMProvider] = None
        self.fallback_provider: Optional[LLMProvider] = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize primary and fallback providers."""
        try:
            if settings.primary_llm_provider == "google":
                self.primary_provider = GoogleGeminiProvider(settings.primary_llm_model)
                logger.info(f"Initialized primary LLM: Google {settings.primary_llm_model}")
            elif settings.primary_llm_provider == "openai":
                self.primary_provider = OpenAIProvider(settings.primary_llm_model)
                logger.info(f"Initialized primary LLM: OpenAI {settings.primary_llm_model}")
        except Exception as e:
            logger.warning(f"Failed to initialize primary LLM: {e}")

        try:
            if settings.fallback_llm_provider == "openai":
                self.fallback_provider = OpenAIProvider(settings.fallback_llm_model)
                logger.info(f"Initialized fallback LLM: OpenAI {settings.fallback_llm_model}")
            elif settings.fallback_llm_provider == "google":
                self.fallback_provider = GoogleGeminiProvider(settings.fallback_llm_model)
                logger.info(f"Initialized fallback LLM: Google {settings.fallback_llm_model}")
        except Exception as e:
            logger.warning(f"Failed to initialize fallback LLM: {e}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Generate with automatic fallback."""
        provider = self.fallback_provider if use_fallback else self.primary_provider

        if not provider:
            raise ValueError("No LLM provider available")

        try:
            return await provider.generate(prompt, system_prompt, temperature, max_tokens)
        except Exception as e:
            logger.error(f"Primary provider failed: {e}")
            if not use_fallback and self.fallback_provider:
                logger.info("Falling back to secondary provider")
                return await self.generate(prompt, system_prompt, temperature, max_tokens, use_fallback=True)
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming with fallback."""
        provider = self.primary_provider
        try:
            async for chunk in provider.generate_stream(prompt, system_prompt, temperature):
                yield chunk
        except Exception as e:
            logger.error(f"Primary provider streaming failed: {e}")
            if self.fallback_provider:
                logger.info("Falling back to secondary provider for streaming")
                async for chunk in self.fallback_provider.generate_stream(
                    prompt, system_prompt, temperature
                ):
                    yield chunk
            else:
                raise

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Generate with tools and automatic fallback."""
        provider = self.fallback_provider if use_fallback else self.primary_provider

        if not provider:
            raise ValueError("No LLM provider available")

        try:
            return await provider.generate_with_tools(messages, tools, temperature, max_tokens)
        except Exception as e:
            logger.error(f"Primary provider failed: {e}")
            if not use_fallback and self.fallback_provider:
                logger.info("Falling back to secondary provider")
                return await self.generate_with_tools(messages, tools, temperature, max_tokens, use_fallback=True)
            raise


# Lazy singleton instance (initialized on first use, not at module import)
_llm_manager_instance: Optional[LLMProviderManager] = None


def get_llm_manager() -> LLMProviderManager:
    """Get or create the global LLM manager instance (lazy initialization)."""
    global _llm_manager_instance
    if _llm_manager_instance is None:
        _llm_manager_instance = LLMProviderManager()
    return _llm_manager_instance


# For backward compatibility, create a property that acts like the old global
# This allows existing code to work without changes
class _LLMManagerProxy:
    """Proxy to provide lazy initialization with same interface as before."""
    
    def __getattr__(self, name):
        return getattr(get_llm_manager(), name)
    
    async def generate(self, *args, **kwargs):
        return await get_llm_manager().generate(*args, **kwargs)
    
    async def generate_with_tools(self, *args, **kwargs):
        return await get_llm_manager().generate_with_tools(*args, **kwargs)


llm_manager = _LLMManagerProxy()

