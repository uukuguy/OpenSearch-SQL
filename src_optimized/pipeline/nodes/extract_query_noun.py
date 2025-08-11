"""
Query noun extraction node for OpenSearch-SQL pipeline.
"""
import logging
import re
from typing import Any, Dict, List

# NLTK imports with fallback
try:
    import nltk
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.tag import pos_tag
    from nltk.chunk import ne_chunk
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logging.warning("NLTK not available, using basic text processing")

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator, get_last_node_result


@node_decorator(check_schema_status=False)
def extract_query_noun(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract important noun phrases and entities from the query.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Extracted nouns, entities, and key phrases.
    """
    try:
        # Get configuration
        config, node_name = PipelineManager().get_model_para()
        
        # Initialize NLTK components (download if needed)
        ensure_nltk_data()
        
        # Extract using multiple methods
        pattern_nouns = extract_nouns_by_pattern(task.question, task.evidence)
        nltk_entities = extract_entities_with_nltk(task.question, task.evidence)
        
        # Use LLM if configured
        llm_entities = []
        use_llm = config.get("use_llm", True)
        if use_llm:
            try:
                engine = config.get("engine", "gpt-4o")
                chat_model = model_chose(node_name, engine)
                llm_entities = extract_entities_with_llm(task.question, task.evidence, chat_model)
            except Exception as e:
                logging.warning(f"LLM extraction failed: {e}")
        
        # Combine and clean results
        all_entities = combine_and_rank_entities(pattern_nouns, nltk_entities, llm_entities)
        
        response = {
            "extracted_nouns": pattern_nouns,
            "named_entities": nltk_entities,
            "llm_entities": llm_entities,
            "combined_entities": all_entities,
            "total_entities": len(all_entities)
        }
        
        logging.info(f"Extracted {len(all_entities)} entities for task {task.db_id}_{task.question_id}")
        return response
        
    except Exception as e:
        logging.error(f"Error in extract_query_noun: {e}")
        return {
            "extracted_nouns": [],
            "named_entities": [],
            "llm_entities": [],
            "combined_entities": [],
            "status": "error",
            "error": str(e)
        }


def ensure_nltk_data():
    """Ensure required NLTK data is downloaded."""
    if not NLTK_AVAILABLE:
        return
        
    required_data = ['punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words']
    
    for data in required_data:
        try:
            nltk.data.find(f'tokenizers/{data}')
        except LookupError:
            try:
                nltk.download(data, quiet=True)
            except Exception as e:
                logging.warning(f"Could not download NLTK data {data}: {e}")


def extract_nouns_by_pattern(question: str, evidence: str) -> List[Dict[str, Any]]:
    """
    Extract nouns using pattern matching.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        
    Returns:
        List[Dict[str, Any]]: Extracted nouns with metadata.
    """
    extracted_nouns = []
    combined_text = f"{question} {evidence}"
    
    try:
        if NLTK_AVAILABLE:
            # Tokenize and get POS tags
            tokens = word_tokenize(combined_text)
            pos_tags = pos_tag(tokens)
        else:
            # Basic tokenization fallback
            tokens = combined_text.split()
            pos_tags = [(token, 'NN') for token in tokens if len(token) > 2]
        
        # Extract nouns (NN, NNS, NNP, NNPS)
        noun_tags = ['NN', 'NNS', 'NNP', 'NNPS']
        for word, tag in pos_tags:
            if tag in noun_tags and len(word) > 2:
                extracted_nouns.append({
                    "word": word,
                    "pos_tag": tag,
                    "type": "noun",
                    "method": "nltk_pos",
                    "confidence": 0.8
                })
        
        # Extract noun phrases (simple patterns)
        noun_phrase_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.findall(noun_phrase_pattern, combined_text)
        for match in matches:
            if len(match.split()) <= 3:
                extracted_nouns.append({
                    "word": match,
                    "pos_tag": "NP",
                    "type": "noun_phrase",
                    "method": "regex_pattern",
                    "confidence": 0.6
                })
        
    except Exception as e:
        logging.warning(f"Error in pattern-based noun extraction: {e}")
    
    return extracted_nouns


def extract_entities_with_nltk(question: str, evidence: str) -> List[Dict[str, Any]]:
    """
    Extract named entities using NLTK.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        
    Returns:
        List[Dict[str, Any]]: Extracted entities with metadata.
    """
    entities = []
    combined_text = f"{question} {evidence}"
    
    try:
        if not NLTK_AVAILABLE:
            return entities
            
        # Tokenize and get POS tags
        tokens = word_tokenize(combined_text)
        pos_tags = pos_tag(tokens)
        
        # Named entity recognition
        tree = ne_chunk(pos_tags)
        
        for subtree in tree:
            if hasattr(subtree, 'label'):
                entity_name = ' '.join([token for token, pos in subtree.leaves()])
                entity_type = subtree.label()
                
                entities.append({
                    "word": entity_name,
                    "entity_type": entity_type,
                    "type": "named_entity",
                    "method": "nltk_ne",
                    "confidence": 0.75
                })
        
    except Exception as e:
        logging.warning(f"Error in NLTK entity extraction: {e}")
    
    return entities


def extract_entities_with_llm(question: str, evidence: str, chat_model) -> List[Dict[str, Any]]:
    """
    Extract entities using LLM analysis.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        chat_model: Chat model instance.
        
    Returns:
        List[Dict[str, Any]]: Extracted entities with metadata.
    """
    try:
        from ...llm.prompts import PromptManager
        prompt_manager = PromptManager()
        
        prompt = prompt_manager.format_prompt(
            "extract_query_noun",
            question=question,
            evidence=evidence
        )
        
        response = chat_model.get_ans(prompt, temperature=0.0)
        
        # Parse LLM response
        entities = parse_llm_noun_response(response)
        
        return entities
        
    except Exception as e:
        logging.warning(f"Error extracting entities with LLM: {e}")
        return []


def parse_llm_noun_response(response: str) -> List[Dict[str, Any]]:
    """
    Parse LLM response to extract structured entity information.
    
    Args:
        response (str): LLM response text.
        
    Returns:
        List[Dict[str, Any]]: Parsed entities with metadata.
    """
    entities = []
    
    try:
        lines = response.split('\n')
        current_category = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for category headers
            if any(header in line.lower() for header in ['entities', 'attributes', 'relationships', 'conditions']):
                current_category = line.lower()
                continue
            
            # Extract items (look for bullets, numbers, or simple lists)
            if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                # Clean the item
                item = re.sub(r'^[•\-*\d.]\s*', '', line).strip()
                if len(item) > 2:
                    entities.append({
                        "word": item,
                        "category": current_category or "general",
                        "type": "llm_entity",
                        "method": "llm_extraction",
                        "confidence": 0.7
                    })
    
    except Exception as e:
        logging.warning(f"Error parsing LLM noun response: {e}")
    
    return entities


def combine_and_rank_entities(pattern_nouns: List[Dict[str, Any]], 
                             nltk_entities: List[Dict[str, Any]],
                             llm_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Combine and rank all extracted entities.
    
    Args:
        pattern_nouns: Entities from pattern matching.
        nltk_entities: Entities from NLTK.
        llm_entities: Entities from LLM.
        
    Returns:
        List[Dict[str, Any]]: Combined and ranked entities.
    """
    all_entities = pattern_nouns + nltk_entities + llm_entities
    
    # Deduplicate based on word similarity
    seen_words = set()
    unique_entities = []
    
    # Sort by confidence descending
    sorted_entities = sorted(all_entities, key=lambda x: x.get('confidence', 0), reverse=True)
    
    for entity in sorted_entities:
        word = entity['word'].lower().strip()
        
        # Skip very short words
        if len(word) < 2:
            continue
            
        # Skip common stop words
        if word in {'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}:
            continue
        
        # Add if not seen (simple deduplication)
        if word not in seen_words:
            seen_words.add(word)
            unique_entities.append(entity)
    
    # Return top entities
    return unique_entities[:15]