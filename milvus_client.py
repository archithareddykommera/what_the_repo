#!/usr/bin/env python3
"""
Milvus client module for querying PRs and files.
Provides utility functions for both scalar queries and vector search.
"""

import os
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, utility
import numpy as np

class MilvusClient:
    """Client for interacting with Milvus vector database"""
    
    def __init__(self):
        self.connection = None
        self.pr_collection = None
        self.file_collection = None
        self.embedding_dim = 1536
        
    def connect(self):
        """Initialize connection to Milvus"""
        try:
            milvus_url = os.getenv('MILVUS_URL')
            milvus_token = os.getenv('MILVUS_TOKEN')
            
            if not milvus_url or not milvus_token:
                raise ValueError("Milvus configuration not found")
            
            # Connect to Milvus
            connections.connect(
                alias="default",
                uri=milvus_url,
                token=milvus_token
            )
            
            # Store connection reference
            self.connection = "default"
            
            # Get collections
            self.pr_collection = Collection("pr_index_what_the_repo")
            self.file_collection = Collection("file_changes_what_the_repo")
            
            print("✅ Milvus connection established")
            
        except Exception as e:
            print(f"❌ Failed to connect to Milvus: {e}")
            raise
    
    def query_prs(self, expr: str, fields: List[str]) -> List[Dict[str, Any]]:
        """
        Query PRs using scalar filters.
        
        Args:
            expr: Scalar expression for filtering
            fields: List of fields to return
            
        Returns:
            List of PR records
        """
        if not self.pr_collection:
            raise ValueError("PR collection not initialized")
        
        try:
            print(f"🔍 Milvus PR Query:")
            print(f"   Expression: {expr}")
            print(f"   Fields: {fields}")
            
            results = self.pr_collection.query(
                expr=expr,
                output_fields=fields,
                limit=1000  # Adjust as needed
            )
            
            print(f"   Raw results count: {len(results)}")
            if results:
                print(f"   Sample raw result: {results[0]}")
            
            # Convert numpy types to Python native types
            converted_results = [self._convert_numpy_types(record) for record in results]
            print(f"   Converted results count: {len(converted_results)}")
            
            return converted_results
            
        except Exception as e:
            print(f"Error querying PRs: {e}")
            return []
    
    def search_prs(self, vec: List[float], expr: str, fields: List[str], k: int = 50) -> List[Dict[str, Any]]:
        """
        Search PRs using vector similarity with scalar pre-filtering.
        
        Args:
            vec: Query vector
            expr: Scalar expression for pre-filtering
            fields: List of fields to return
            k: Number of results to return
            
        Returns:
            List of PR records with similarity scores
        """
        if not self.pr_collection:
            raise ValueError("PR collection not initialized")
        
        try:
            # Load collection
            self.pr_collection.load()
            
            # Perform vector search with scalar filter
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            print(f"🔍 Milvus PR Vector Search:")
            print(f"   Expression: {expr}")
            print(f"   Fields: {fields}")
            print(f"   Search params: {search_params}")
            
            results = self.pr_collection.search(
                data=[vec],
                anns_field="vector",
                param=search_params,
                expr=expr,
                output_fields=fields,
                limit=k
            )
            
            print(f"   Raw search results: {len(results)} result sets")
            
            # Convert results to list of dictionaries
            search_results = []
            for hits in results:
                for hit in hits:
                    record = hit.entity.to_dict()
                    record['_distance'] = hit.distance
                    record['_id'] = hit.id
                    search_results.append(self._convert_numpy_types(record))
            
            print(f"   Converted search results: {len(search_results)}")
            if search_results:
                print(f"   Sample search result: {search_results[0]}")
            
            return search_results
            
        except Exception as e:
            print(f"Error searching PRs: {e}")
            return []
    
    def query_files(self, expr: str, fields: List[str]) -> List[Dict[str, Any]]:
        """
        Query files using scalar filters.
        
        Args:
            expr: Scalar expression for filtering
            fields: List of fields to return
            
        Returns:
            List of file records
        """
        if not self.file_collection:
            raise ValueError("File collection not initialized")
        
        try:
            print(f"🔍 Milvus File Query:")
            print(f"   Expression: {expr}")
            print(f"   Fields: {fields}")
            
            results = self.file_collection.query(
                expr=expr,
                output_fields=fields,
                limit=1000  # Adjust as needed
            )
            
            print(f"   Raw results count: {len(results)}")
            if results:
                print(f"   Sample raw result: {results[0]}")
            
            # Convert numpy types to Python native types
            converted_results = [self._convert_numpy_types(record) for record in results]
            print(f"   Converted results count: {len(converted_results)}")
            
            return converted_results
            
        except Exception as e:
            print(f"Error querying files: {e}")
            return []
    
    def search_files(self, vec: List[float], expr: str, fields: List[str], k: int = 50) -> List[Dict[str, Any]]:
        """
        Search files using vector similarity with scalar pre-filtering.
        
        Args:
            vec: Query vector
            expr: Scalar expression for pre-filtering
            fields: List of fields to return
            k: Number of results to return
            
        Returns:
            List of file records with similarity scores
        """
        if not self.file_collection:
            raise ValueError("File collection not initialized")
        
        try:
            # Load collection
            self.file_collection.load()
            
            # Perform vector search with scalar filter
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            print(f"🔍 Milvus File Vector Search:")
            print(f"   Expression: {expr}")
            print(f"   Fields: {fields}")
            print(f"   Search params: {search_params}")
            
            results = self.file_collection.search(
                data=[vec],
                anns_field="vector",
                param=search_params,
                expr=expr,
                output_fields=fields,
                limit=k
            )
            
            print(f"   Raw search results: {len(results)} result sets")
            
            # Convert results to list of dictionaries
            search_results = []
            for hits in results:
                for hit in hits:
                    record = hit.entity.to_dict()
                    record['_distance'] = hit.distance
                    record['_id'] = hit.id
                    search_results.append(self._convert_numpy_types(record))
            
            print(f"   Converted search results: {len(search_results)}")
            if search_results:
                print(f"   Sample search result: {search_results[0]}")
            
            return search_results
            
        except Exception as e:
            print(f"Error searching files: {e}")
            return []
    
    def _convert_numpy_types(self, obj: Any) -> Any:
        """Convert numpy types to Python native types"""
        if isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        elif hasattr(obj, 'tolist'):  # numpy array
            return obj.tolist()
        else:
            return obj
    
    def close(self):
        """Close Milvus connection"""
        if self.connection:
            connections.disconnect(self.connection)
            print("✅ Milvus connection closed")

# Global Milvus client instance
milvus_client = None

def get_milvus_client() -> MilvusClient:
    """Get or create global Milvus client instance"""
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient()
        milvus_client.connect()
    return milvus_client

def query_prs(expr: str, fields: List[str]) -> List[Dict[str, Any]]:
    """Utility function to query PRs"""
    client = get_milvus_client()
    return client.query_prs(expr, fields)

def search_prs(vec: List[float], expr: str, fields: List[str], k: int = 50) -> List[Dict[str, Any]]:
    """Utility function to search PRs"""
    client = get_milvus_client()
    return client.search_prs(vec, expr, fields, k)

def query_files(expr: str, fields: List[str]) -> List[Dict[str, Any]]:
    """Utility function to query files"""
    client = get_milvus_client()
    return client.query_files(expr, fields)

def search_files(vec: List[float], expr: str, fields: List[str], k: int = 50) -> List[Dict[str, Any]]:
    """Utility function to search files"""
    client = get_milvus_client()
    return client.search_files(vec, expr, fields, k)
