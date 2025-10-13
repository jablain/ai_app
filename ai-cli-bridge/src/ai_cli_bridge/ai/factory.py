"""Factory for creating AI instances."""

from typing import Dict, Any
from .base import BaseAI


class AIFactory:
    """
    Factory class for creating AI instances.
    
    Manages registration and instantiation of AI implementations.
    """
    
    _registry: Dict[str, type[BaseAI]] = {}
    
    @classmethod
    def register(cls, ai_name: str, ai_class: type[BaseAI]) -> None:
        """
        Register an AI implementation.
        
        Args:
            ai_name: Lowercase AI identifier (e.g., 'claude', 'chatgpt')
            ai_class: AI class that inherits from BaseAI
        """
        normalized_name = ai_name.lower().strip()
        cls._registry[normalized_name] = ai_class
    
    
    @classmethod
    def get_class(cls, ai_name: str) -> type[BaseAI]:
        """
        Get the AI class without instantiating it.
        
        Args:
            ai_name: AI identifier (e.g., 'claude', 'chatgpt')
            
        Returns:
            The AI class (not an instance)
            
        Raises:
            ValueError: If AI name is not registered
        """
        normalized_name = ai_name.lower().strip()
        
        if normalized_name not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown AI: '{ai_name}'. "
                f"Available: {available}"
            )
        
        return cls._registry[normalized_name]
    
    
    @classmethod
    def create(cls, ai_name: str, config: Dict[str, Any]) -> BaseAI:
        """
        Create an AI instance.
        
        Args:
            ai_name: AI identifier (e.g., 'claude', 'chatgpt')
            config: Configuration dictionary
            
        Returns:
            Instance of the appropriate AI class
            
        Raises:
            ValueError: If AI name is not registered
        """
        ai_class = cls.get_class(ai_name)
        return ai_class(config)
    
    
    @classmethod
    def list_available(cls) -> list[str]:
        """
        List all registered AI names.
        
        Returns:
            List of lowercase AI identifiers
        """
        return sorted(cls._registry.keys())
    
    
    @classmethod
    def is_registered(cls, ai_name: str) -> bool:
        """
        Check if an AI is registered.
        
        Args:
            ai_name: AI identifier
            
        Returns:
            True if registered, False otherwise
        """
        return ai_name.lower().strip() in cls._registry
