from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import logging
from typing import List, Dict, Set

@dataclass
class DocumentMetadata:
    """Store document metadata"""
    file_path: str
    contract_type: str
    expiry_date: str
    company_name: str
    last_modified: datetime
    file_hash: str

class DocumentIndex:
    def __init__(self, cache_dir=".cache"):
        self.cache_dir = cache_dir
        self.metadata = {}
        self.embeddings = {}
        self._ensure_cache_dir()
        self.load_cache()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
    def load_cache(self):
        """Load cached metadata and embeddings"""
        try:
            metadata_path = os.path.join(self.cache_dir, "metadata.json")
            embeddings_path = os.path.join(self.cache_dir, "embeddings.json")
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                    
            if os.path.exists(embeddings_path):
                with open(embeddings_path, 'r') as f:
                    self.embeddings = json.load(f)
                    
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            self.metadata = {}
            self.embeddings = {}
            
    def save_cache(self):
        """Save current metadata and embeddings to cache"""
        try:
            metadata_path = os.path.join(self.cache_dir, "metadata.json")
            embeddings_path = os.path.join(self.cache_dir, "embeddings.json")
            
            with open(metadata_path, 'w') as f:
                json.dump(self.metadata, f)
                
            with open(embeddings_path, 'w') as f:
                json.dump(self.embeddings, f)
                
        except Exception as e:
            logging.error(f"Error saving cache: {str(e)}")
            
    def get_file_hash(self, file_path: str) -> str:
        """Calculate file hash to detect changes"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logging.error(f"Error calculating file hash: {str(e)}")
            return ""
            
    def sync_files(self, current_files: List[str]) -> Set[str]:
        """Sync index with current files and return changed files"""
        changed_files = set()
        current_file_set = set(current_files)
        
        # Check for new or modified files
        for file_path in current_files:
            current_hash = self.get_file_hash(file_path)
            
            if file_path not in self.metadata or self.metadata[file_path]['file_hash'] != current_hash:
                changed_files.add(file_path)
                
        # Remove deleted files
        for file_path in list(self.metadata.keys()):
            if file_path not in current_file_set:
                del self.metadata[file_path]
                if file_path in self.embeddings:
                    del self.embeddings[file_path]
                    
        self.save_cache()
        return changed_files
        
    def update_document(self, file_path: str, metadata: Dict, embeddings: List[float] = None):
        """Update document metadata and embeddings"""
        self.metadata[file_path] = {
            **metadata,
            'file_hash': self.get_file_hash(file_path),
            'last_modified': datetime.now().isoformat()
        }
        
        if embeddings is not None:
            self.embeddings[file_path] = embeddings
            
        self.save_cache()
        
    def get_document_metadata(self, file_path: str) -> Dict:
        """Get metadata for a specific document"""
        return self.metadata.get(file_path, {})
        
    def get_all_metadata(self) -> Dict:
        """Get metadata for all documents"""
        return self.metadata
        
    def get_embeddings(self, file_path: str) -> List[float]:
        """Get embeddings for a specific document"""
        return self.embeddings.get(file_path, [])
