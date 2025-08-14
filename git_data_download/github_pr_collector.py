import os
import requests
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any
import time
import base64
import re

# Try to import openai, but don't fail if it's not available
try:
    import openai
except ImportError:
    openai = None

class GitHubPRCollector:
    def __init__(self, github_token: str):
        """
        Initialize the GitHub PR Collector
        
        Args:
            github_token (str): GitHub API token from environment variable
        """
        self.github_token = github_token
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        
        # Initialize OpenAI client if API key is available
        self.openai_client = None
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            try:
                # Use the newer OpenAI client
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_api_key)
                print("[PASS] OpenAI client initialized successfully")
            except ImportError:
                # Fallback to older openai library
                openai.api_key = openai_api_key
                self.openai_client = openai
                print("[PASS] OpenAI client initialized (legacy mode)")
        else:
            print("Warning: OPENAI_API_KEY not found. File summaries will not be generated.")
    
    def _generate_file_summary(self, filename: str, pre_content: str, post_content: str, diff: str, language: str) -> str:
        """
        Generate a summary of file changes using LLM
        
        Args:
            filename (str): Name of the file
            pre_content (str): Content before changes
            post_content (str): Content after changes
            diff (str): Git diff/patch
            language (str): Programming language
            
        Returns:
            str: Generated summary
        """
        if not self.openai_client:
            return "Summary not available (OpenAI API key not configured)"
        
        try:
            # Prepare the prompt for the LLM
            prompt = f"""
            Analyze the changes made to the file '{filename}' (Language: {language}).
            
            Here's the git diff/patch showing the changes:
            {diff}
            
            Please provide a concise summary (2-3 sentences) of what was changed in this file. Focus on:
            1. What functionality was added, modified, or removed
            2. The impact of these changes
            3. Any notable patterns or improvements
            
            Summary:
            """
            
            # Call OpenAI API
            try:
                # Try newer OpenAI client first
                if hasattr(self.openai_client, 'chat'):
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that analyzes code changes and provides concise summaries."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=200,
                        temperature=0.3
                    )
                    summary = response.choices[0].message.content.strip()
                else:
                    # Fallback to older openai library
                    response = self.openai_client.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that analyzes code changes and provides concise summaries."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=200,
                        temperature=0.3
                    )
                    summary = response.choices[0].message.content.strip()
            except Exception as api_error:
                print(f"OpenAI API error: {api_error}")
                return f"Error calling OpenAI API: {str(api_error)}"
            return summary
            
        except Exception as e:
            return f"Error generating summary: {str(e)}"
    
    def get_repo_pull_requests(self, repo_name: str, state: str = 'all', max_prs: int = None) -> List[Dict[str, Any]]:
        """
        Fetch pull requests for a given repository
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            state (str): PR state filter ('open', 'closed', 'all')
            max_prs (int, optional): Maximum number of PRs to fetch. If None, fetches all PRs.
            
        Returns:
            List[Dict[str, Any]]: List of pull request data
        """
        all_prs = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub API
        
        print(f"Fetching pull requests for repository: {repo_name}")
        
        while True:
            url = f"{self.base_url}/repos/{repo_name}/pulls"
            params = {
                'state': state,
                'per_page': per_page,
                'page': page,
                'sort': 'created',
                'direction': 'desc'
            }
            
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                prs = response.json()
                
                if not prs:  # No more PRs to fetch
                    break
                    
                # Process each PR and extract required metadata
                for i, pr in enumerate(prs):
                    pr_number = pr.get('number', 'unknown')
                    print(f"Processing PR #{pr_number} ({i+1}/{len(prs)} on page {page})")
                    try:
                        pr_data = self._extract_pr_metadata(pr, repo_name)
                        if pr_data:  # Only add if we got valid data
                            all_prs.append(pr_data)
                        else:
                            print(f"Warning: Could not extract metadata for PR #{pr_number}")
                    except Exception as e:
                        print(f"Error processing PR #{pr_number}: {e}")
                        continue
                    
                    # Check if we've reached the maximum number of PRs
                    if max_prs and len(all_prs) >= max_prs:
                        print(f"Reached maximum PR limit ({max_prs}). Stopping fetch.")
                        break
                
                # Check if we've reached the last page or max PRs
                if len(prs) < per_page or (max_prs and len(all_prs) >= max_prs):
                    break
                    
                page += 1
                
                # Rate limiting: GitHub allows 5000 requests per hour for authenticated users
                # We'll add a small delay to be respectful
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching PRs: {e}")
                break
                
        print(f"Total PRs collected: {len(all_prs)}")
        return all_prs
    
    def get_specific_pr(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        """
        Fetch a specific pull request by number
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            pr_number (int): Pull request number
            
        Returns:
            Dict[str, Any]: Pull request data with all metadata
        """
        # Get detailed PR info
        detailed_pr = self._get_detailed_pr_info(repo_name, pr_number)
        
        if not detailed_pr:
            print(f"Error: Could not fetch PR #{pr_number}")
            return {}
        
        # Create a mock PR object that matches the structure expected by _extract_pr_metadata
        # The detailed PR data is already complete, so we just need to ensure it has the 'number' field
        mock_pr = detailed_pr.copy()
        if 'number' not in mock_pr:
            mock_pr['number'] = pr_number
        
        # Extract metadata using the same method as get_repo_pull_requests
        try:
            pr_data = self._extract_pr_metadata(mock_pr, repo_name)
            return pr_data
        except Exception as e:
            print(f"Error extracting metadata for PR #{pr_number}: {e}")
            return {}
    
    def _get_repo_info(self, repo_name: str) -> Dict[str, Any]:
        """
        Get repository information including repo_id
        
        Args:
            repo_name (str): Repository name (owner/repo)
            
        Returns:
            Dict[str, Any]: Repository information
        """
        url = f"{self.base_url}/repos/{repo_name}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Add a small delay to respect rate limits
            time.sleep(0.1)
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching repository info for {repo_name}: {e}")
            return {}
    
    def _get_detailed_pr_info(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        """
        Fetch detailed information for a specific pull request
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            pr_number (int): Pull request number
            
        Returns:
            Dict[str, Any]: Detailed PR information
        """
        url = f"{self.base_url}/repos/{repo_name}/pulls/{pr_number}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Add a small delay to respect rate limits
            time.sleep(0.1)
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching detailed info for PR #{pr_number}: {e}")
            return {}
    
    def _get_pr_files(self, repo_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch detailed file information for a specific pull request
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            pr_number (int): Pull request number
            
        Returns:
            List[Dict[str, Any]]: List of file information
        """
        url = f"{self.base_url}/repos/{repo_name}/pulls/{pr_number}/files"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Add a small delay to respect rate limits
            time.sleep(0.1)
            
            files_data = response.json()
            
            # Check if this is a very large PR that might cause issues
            if len(files_data) > 1000:
                print(f"Warning: PR #{pr_number} has {len(files_data)} files - processing only first 100 files")
                files_data = files_data[:100]
            
            # Process each file to extract detailed metadata
            processed_files = []
            for i, file_data in enumerate(files_data):
                file_info = {
                    'sha': file_data.get('sha'),
                    'filename': file_data.get('filename'),
                    'status': file_data.get('status'),
                    'additions': file_data.get('additions', 0),
                    'deletions': file_data.get('deletions', 0),
                    'changes': file_data.get('changes', 0),
                    'blob_url': file_data.get('blob_url'),
                    'raw_url': file_data.get('raw_url'),
                    'contents_url': file_data.get('contents_url'),
                    'patch': file_data.get('patch'),
                    'previous_filename': file_data.get('previous_filename'),
                    'size': file_data.get('size', 0),
                    'language': self._detect_language(file_data.get('filename', '')),
                    'file_extension': self._get_file_extension(file_data.get('filename', '')),
                    'is_binary': self._is_binary_file(file_data.get('filename', '')),
                    'is_config_file': self._is_config_file(file_data.get('filename', '')),
                    'is_documentation': self._is_documentation_file(file_data.get('filename', '')),
                    'is_test_file': self._is_test_file(file_data.get('filename', '')),
                    'is_source_code': self._is_source_code_file(file_data.get('filename', '')),
                    'change_type': self._get_change_type(file_data.get('status', '')),
                    'lines_added': file_data.get('additions', 0),
                    'lines_deleted': file_data.get('deletions', 0),
                    'lines_changed': file_data.get('changes', 0),
                    'net_lines': (file_data.get('additions', 0) - file_data.get('deletions', 0))
                }
                
                # Generate risk assessment for all files
                if self.openai_client:
                    file_info['risk_assessment'] = self._generate_file_risk_assessment(
                        repo_name, pr_number, file_info
                    )
                
                processed_files.append(file_info)
            
            return processed_files
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching files for PR #{pr_number}: {e}")
            return []
    
    def _get_file_contents(self, repo_name: str, file_path: str, ref: str = 'main') -> Dict[str, Any]:
        """
        Fetch file contents using GitHub Contents API
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            file_path (str): Path to the file in the repository
            ref (str): Git reference (branch, commit SHA, etc.)
            
        Returns:
            Dict[str, Any]: File content information
        """
        url = f"{self.base_url}/repos/{repo_name}/contents/{file_path}"
        params = {'ref': ref}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 404:
                return {'content': None, 'encoding': None, 'size': 0, 'error': 'File not found'}
            
            response.raise_for_status()
            
            # Add a small delay to respect rate limits
            time.sleep(0.1)
            
            content_data = response.json()
            
            # Handle single file response
            if isinstance(content_data, dict) and 'content' in content_data:
                return {
                    'content': content_data.get('content'),
                    'encoding': content_data.get('encoding'),
                    'size': content_data.get('size', 0),
                    'sha': content_data.get('sha'),
                    'url': content_data.get('url'),
                    'download_url': content_data.get('download_url')
                }
            
            return {'content': None, 'encoding': None, 'size': 0, 'error': 'Unexpected response format'}
            
        except requests.exceptions.RequestException as e:
            return {'content': None, 'encoding': None, 'size': 0, 'error': str(e)}
    
    def _decode_and_analyze_content(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decode base64 content and perform basic analysis
        
        Args:
            content_data (Dict[str, Any]): File content data from GitHub API
            
        Returns:
            Dict[str, Any]: Enhanced content data with decoded content and analysis
        """
        if not content_data:
            return {'content': None, 'encoding': None, 'size': 0, 'error': 'No content data provided'}
        
        if not content_data.get('content'):
            return content_data
        
        try:
            # Decode base64 content
            encoded_content = content_data.get('content', '')
            if content_data.get('encoding') == 'base64':
                decoded_content = base64.b64decode(encoded_content).decode('utf-8', errors='ignore')
                content_data['decoded_content'] = decoded_content
                
                # Basic content analysis
                lines = decoded_content.split('\n')
                content_data['analysis'] = {
                    'total_lines': len(lines),
                    'non_empty_lines': len([line for line in lines if line.strip()]),
                    'empty_lines': len([line for line in lines if not line.strip()]),
                    'total_characters': len(decoded_content),
                    'total_words': len(re.findall(r'\b\w+\b', decoded_content)),
                    'has_comments': any('//' in line or '#' in line or '/*' in line for line in lines),
                    'has_functions': any('def ' in line or 'function ' in line or 'public ' in line for line in lines),
                    'has_classes': any('class ' in line for line in lines),
                    'has_imports': any('import ' in line or 'from ' in line or '#include' in line for line in lines)
                }
            else:
                content_data['decoded_content'] = encoded_content
                content_data['analysis'] = {
                    'total_lines': 0,
                    'non_empty_lines': 0,
                    'empty_lines': 0,
                    'total_characters': len(encoded_content),
                    'total_words': 0,
                    'has_comments': False,
                    'has_functions': False,
                    'has_classes': False,
                    'has_imports': False
                }
                
        except Exception as e:
            content_data['decoded_content'] = None
            content_data['analysis'] = None
            content_data['decode_error'] = str(e)
        
        return content_data
    
    def _get_merged_pr_file_contents(self, repo_name: str, pr_number: int, files_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fetch pre/post file contents for merged PRs and generate summaries and risk assessments
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            pr_number (int): Pull request number
            files_info (List[Dict[str, Any]]): List of file information
            
        Returns:
            List[Dict[str, Any]]: Enhanced file information with contents, summaries, and risk assessments
        """
        # Get PR details to find base and head branches
        pr_details = self._get_detailed_pr_info(repo_name, pr_number)
        
        # Handle case where pr_details is None
        if pr_details is None:
            pr_details = {}
        
        base_branch = pr_details.get('base', {}).get('ref', 'main')
        head_branch = pr_details.get('head', {}).get('ref', 'main')
        
        enhanced_files = []
        
        for file_info in files_info:
            filename = file_info.get('filename')
            status = file_info.get('status')
            language = file_info.get('language', 'Unknown')
            diff = file_info.get('patch', '')
            
            if not filename:
                continue
            
            # Initialize content fields
            file_info['post_content'] = None
            file_info['post_content_sha'] = None
            file_info['content_error'] = None
            file_info['ai_summary'] = None
            file_info['risk_assessment'] = None
            
            try:
                if status == 'added':
                    # File was added - only get post content (head branch)
                    post_content = self._get_file_contents(repo_name, filename, head_branch)
                    if post_content.get('content'):
                        post_content = self._decode_and_analyze_content(post_content)
                    file_info['post_content'] = post_content.get('decoded_content')
                    file_info['post_content_sha'] = post_content.get('sha')
                    
                    # Generate summary for added files
                    if self.openai_client:
                        file_info['ai_summary'] = self._generate_file_summary(
                            filename, "", post_content.get('decoded_content', ''), diff, language
                        )
                    
                elif status == 'removed':
                    # File was removed - get pre content for summary, but don't save it
                    pre_content = self._get_file_contents(repo_name, filename, base_branch)
                    if pre_content.get('content'):
                        pre_content = self._decode_and_analyze_content(pre_content)
                    
                    # Generate summary for removed files
                    if self.openai_client:
                        file_info['ai_summary'] = self._generate_file_summary(
                            filename, pre_content.get('decoded_content', ''), "", diff, language
                        )
                    
                elif status in ['modified', 'renamed']:
                    # File was modified or renamed - get both pre and post content for summary
                    pre_content = self._get_file_contents(repo_name, filename, base_branch)
                    if pre_content.get('content'):
                        pre_content = self._decode_and_analyze_content(pre_content)
                    
                    # For renamed files, check if the new filename exists
                    post_filename = filename
                    if status == 'renamed' and file_info.get('previous_filename'):
                        post_filename = filename  # Current filename is the new one
                    
                    post_content = self._get_file_contents(repo_name, post_filename, head_branch)
                    if post_content.get('content'):
                        post_content = self._decode_and_analyze_content(post_content)
                    
                    # Only save post content
                    file_info['post_content'] = post_content.get('decoded_content')
                    file_info['post_content_sha'] = post_content.get('sha')
                    
                    # Generate summary for modified/renamed files
                    if self.openai_client:
                        file_info['ai_summary'] = self._generate_file_summary(
                            filename, 
                            pre_content.get('decoded_content', ''), 
                            post_content.get('decoded_content', ''), 
                            diff, 
                            language
                        )
                
                # Check for content errors
                if pre_content and pre_content.get('error'):
                    file_info['content_error'] = f"Pre content error: {pre_content.get('error')}"
                elif post_content and post_content.get('error'):
                    file_info['content_error'] = f"Post content error: {post_content.get('error')}"
                
                # Generate risk assessment for all files
                if self.openai_client:
                    file_info['risk_assessment'] = self._generate_file_risk_assessment(
                        repo_name, pr_number, file_info
                    )
                
            except Exception as e:
                file_info['content_error'] = f"Error fetching content: {str(e)}"
            
            enhanced_files.append(file_info)
        
        return enhanced_files
    
    def _generate_pr_summary(self, pr_data: Dict[str, Any]) -> str:
        """
        Generate a PR-level summary using file summaries or PR metadata
        
        Args:
            pr_data (Dict[str, Any]): Complete PR data including files and metadata
            
        Returns:
            str: Generated PR summary
        """
        if not self.openai_client:
            return "Summary not available (OpenAI API key not configured)"
        
        try:
            # Check if PR is merged and has file summaries
            is_merged = pr_data.get('is_merged', False)
            files = pr_data.get('files', [])
            file_summaries = [f.get('ai_summary') for f in files if f.get('ai_summary') and f.get('ai_summary') != "Summary not available (OpenAI API key not configured)"]
            
            if is_merged and file_summaries:
                # Use file summaries for merged PRs
                prompt = f"""
                Analyze the following pull request based on its file-level changes.
                
                PR Title: {pr_data.get('title', 'No title')}
                PR Description: {pr_data.get('body', 'No description')}
                Files Changed: {len(files)}
                Total Additions: {pr_data.get('additions', 0)}
                Total Deletions: {pr_data.get('deletions', 0)}
                
                File-level summaries:
                {chr(10).join([f"- {summary}" for summary in file_summaries])}
                
                Please provide a comprehensive PR-level summary (3-4 sentences) that:
                1. Describes the overall purpose and impact of the changes
                2. Highlights the key modifications across all files
                3. Mentions the scope and complexity of the changes
                4. Notes any patterns or architectural decisions
                
                PR Summary:
                """
            else:
                # Use PR metadata for unmerged PRs or PRs without file summaries
                prompt = f"""
                Analyze the following pull request based on its metadata.
                
                PR Title: {pr_data.get('title', 'No title')}
                PR Description: {pr_data.get('body', 'No description')}
                Files Changed: {pr_data.get('changed_files', 0)}
                Total Additions: {pr_data.get('additions', 0)}
                Total Deletions: {pr_data.get('deletions', 0)}
                Commits: {pr_data.get('commits', 0)}
                Comments: {pr_data.get('comments', 0)}
                State: {pr_data.get('state', 'unknown')}
                Is Merged: {pr_data.get('is_merged', False)}
                
                Please provide a comprehensive PR-level summary (3-4 sentences) that:
                1. Describes the overall purpose and intended changes
                2. Analyzes the scope and complexity based on metadata
                3. Considers the PR state and activity level
                4. Provides insights about the change impact
                
                PR Summary:
                """
            
            # Call OpenAI API
            try:
                # Try newer OpenAI client first
                if hasattr(self.openai_client, 'chat'):
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that analyzes pull requests and provides comprehensive summaries."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=300,
                        temperature=0.3
                    )
                    summary = response.choices[0].message.content.strip()
                else:
                    # Fallback to older openai library
                    response = self.openai_client.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that analyzes pull requests and provides comprehensive summaries."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=300,
                        temperature=0.3
                    )
                    summary = response.choices[0].message.content.strip()
            except Exception as api_error:
                print(f"OpenAI API error for PR #{pr_data.get('pr_number')}: {api_error}")
                return f"Error calling OpenAI API: {str(api_error)}"
            
            return summary
            
        except Exception as e:
            return f"Error generating PR summary: {str(e)}"
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language based on file extension"""
        extension = self._get_file_extension(filename).lower()
        language_map = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.java': 'Java',
            '.cpp': 'C++', '.c': 'C', '.cs': 'C#', '.php': 'PHP', '.rb': 'Ruby',
            '.go': 'Go', '.rs': 'Rust', '.swift': 'Swift', '.kt': 'Kotlin',
            '.scala': 'Scala', '.clj': 'Clojure', '.hs': 'Haskell', '.ml': 'OCaml',
            '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS', '.sass': 'Sass',
            '.sql': 'SQL', '.r': 'R', '.m': 'MATLAB', '.sh': 'Shell',
            '.yaml': 'YAML', '.yml': 'YAML', '.json': 'JSON', '.xml': 'XML',
            '.md': 'Markdown', '.txt': 'Text', '.rst': 'reStructuredText',
            '.dockerfile': 'Dockerfile', '.dockerignore': 'Docker',
            '.gitignore': 'Git', '.gitattributes': 'Git'
        }
        return language_map.get(extension, 'Unknown')
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        if '.' in filename:
            return '.' + filename.split('.')[-1]
        return ''
    
    def _is_binary_file(self, filename: str) -> bool:
        """Check if file is likely binary"""
        binary_extensions = {'.exe', '.dll', '.so', '.dylib', '.bin', '.dat', '.zip', 
                           '.tar', '.gz', '.rar', '.7z', '.png', '.jpg', '.jpeg', 
                           '.gif', '.bmp', '.ico', '.pdf', '.doc', '.docx', '.xls', 
                           '.xlsx', '.ppt', '.pptx', '.mp3', '.mp4', '.avi', '.mov'}
        return self._get_file_extension(filename).lower() in binary_extensions
    
    def _is_config_file(self, filename: str) -> bool:
        """Check if file is a configuration file"""
        config_patterns = ['config', 'conf', 'ini', 'cfg', 'properties', 'env', 
                          'dockerfile', 'docker-compose', 'package.json', 'requirements.txt',
                          'pom.xml', 'build.gradle', 'cargo.toml', 'go.mod', 'composer.json']
        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in config_patterns)
    
    def _is_documentation_file(self, filename: str) -> bool:
        """Check if file is documentation"""
        doc_extensions = {'.md', '.rst', '.txt', '.pdf', '.doc', '.docx'}
        doc_patterns = ['readme', 'license', 'changelog', 'contributing', 'docs/', 'documentation/']
        filename_lower = filename.lower()
        return (self._get_file_extension(filename).lower() in doc_extensions or
                any(pattern in filename_lower for pattern in doc_patterns))
    
    def _is_test_file(self, filename: str) -> bool:
        """Check if file is a test file"""
        test_patterns = ['test', 'spec', 'specs', 'test_', '_test', 'tests/', 'specs/']
        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in test_patterns)
    
    def _is_source_code_file(self, filename: str) -> bool:
        """Check if file is source code"""
        source_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', 
                           '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.clj', 
                           '.hs', '.ml', '.html', '.css', '.scss', '.sql', '.r', '.sh'}
        return (self._get_file_extension(filename).lower() in source_extensions and
                not self._is_test_file(filename) and not self._is_config_file(filename))
    
    def _get_change_type(self, status: str) -> str:
        """Get human-readable change type"""
        change_types = {
            'added': 'Added',
            'modified': 'Modified', 
            'removed': 'Removed',
            'renamed': 'Renamed'
        }
        return change_types.get(status, status.capitalize())
    
    def _calculate_file_statistics(self, files_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics from file information
        
        Args:
            files_info (List[Dict[str, Any]]): List of file information
            
        Returns:
            Dict[str, Any]: File statistics
        """
        if not files_info:
            return {
                'total_files': 0,
                'total_additions': 0,
                'total_deletions': 0,
                'total_changes': 0,
                'net_lines': 0,
                'languages': {},
                'file_types': {},
                'change_types': {},
                'largest_file': None,
                'most_changed_file': None
            }
        
        # Basic counts
        total_files = len(files_info)
        total_additions = sum(f.get('additions', 0) for f in files_info)
        total_deletions = sum(f.get('deletions', 0) for f in files_info)
        total_changes = sum(f.get('changes', 0) for f in files_info)
        net_lines = total_additions - total_deletions
        
        # Language distribution
        languages = {}
        for file_info in files_info:
            lang = file_info.get('language', 'Unknown')
            languages[lang] = languages.get(lang, 0) + 1
        
        # File type distribution
        file_types = {}
        for file_info in files_info:
            file_type = file_info.get('file_extension', 'no_extension')
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        # Change type distribution
        change_types = {}
        for file_info in files_info:
            change_type = file_info.get('status', 'unknown')
            change_types[change_type] = change_types.get(change_type, 0) + 1
        
        # Find largest file (by changes)
        largest_file = max(files_info, key=lambda x: x.get('changes', 0)) if files_info else None
        largest_file_info = {
            'filename': largest_file.get('filename'),
            'changes': largest_file.get('changes', 0),
            'additions': largest_file.get('additions', 0),
            'deletions': largest_file.get('deletions', 0)
        } if largest_file else None
        
        # Find most changed file (by net lines)
        most_changed_file = max(files_info, key=lambda x: abs(x.get('net_lines', 0))) if files_info else None
        most_changed_file_info = {
            'filename': most_changed_file.get('filename'),
            'net_lines': most_changed_file.get('net_lines', 0),
            'additions': most_changed_file.get('additions', 0),
            'deletions': most_changed_file.get('deletions', 0)
        } if most_changed_file else None
        
        # File category counts
        binary_files = sum(1 for f in files_info if f.get('is_binary', False))
        config_files = sum(1 for f in files_info if f.get('is_config_file', False))
        doc_files = sum(1 for f in files_info if f.get('is_documentation', False))
        test_files = sum(1 for f in files_info if f.get('is_test_file', False))
        source_files = sum(1 for f in files_info if f.get('is_source_code', False))
        
        # Risk assessment statistics
        risk_scores = []
        high_risk_files = 0
        
        for f in files_info:
            risk_assessment = f.get('risk_assessment')
            if risk_assessment and isinstance(risk_assessment, dict):
                risk_score = risk_assessment.get('risk_score_file', 0)
                risk_scores.append(risk_score)
                if risk_assessment.get('high_risk_flag', False):
                    high_risk_files += 1
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        max_risk_score = max(risk_scores) if risk_scores else 0
        min_risk_score = min(risk_scores) if risk_scores else 0
        
        # Content analysis for merged PRs
        content_analysis = {
            'files_with_pre_content': sum(1 for f in files_info if f.get('pre_content')),
            'files_with_post_content': sum(1 for f in files_info if f.get('post_content')),
            'total_pre_lines': 0,  # Removed detailed analysis
            'total_post_lines': 0,  # Removed detailed analysis
            'total_pre_words': 0,   # Removed detailed analysis
            'total_post_words': 0,  # Removed detailed analysis
            'files_with_functions': 0,  # Removed detailed analysis
            'files_with_classes': 0,    # Removed detailed analysis
            'files_with_imports': 0,    # Removed detailed analysis
            'files_with_ai_summaries': sum(1 for f in files_info if f.get('ai_summary')),
            'ai_summaries_available': any(f.get('ai_summary') for f in files_info),
            'pr_summary_available': True,  # PR summaries are now always generated
            'files_with_risk_assessments': sum(1 for f in files_info if f.get('risk_assessment') and isinstance(f.get('risk_assessment'), dict)),
            'risk_assessments_available': any(f.get('risk_assessment') and isinstance(f.get('risk_assessment'), dict) for f in files_info)
        }
        
        return {
            'total_files': total_files,
            'total_additions': total_additions,
            'total_deletions': total_deletions,
            'total_changes': total_changes,
            'net_lines': net_lines,
            'languages': languages,
            'file_types': file_types,
            'change_types': change_types,
            'file_categories': {
                'binary_files': binary_files,
                'config_files': config_files,
                'documentation_files': doc_files,
                'test_files': test_files,
                'source_code_files': source_files
            },
            'risk_assessment': {
                'total_files_with_risk_assessment': len(risk_scores),
                'high_risk_files': high_risk_files,
                'average_risk_score': round(avg_risk_score, 2),
                'max_risk_score': max_risk_score,
                'min_risk_score': min_risk_score,
                'risk_score_distribution': {
                    'low_risk_0_3': sum(1 for score in risk_scores if 0 <= score <= 3),
                    'medium_risk_4_6': sum(1 for score in risk_scores if 4 <= score <= 6),
                    'high_risk_7_10': sum(1 for score in risk_scores if 7 <= score <= 10)
                }
            },
            'largest_file': largest_file_info,
            'most_changed_file': most_changed_file_info,
            'average_changes_per_file': total_changes / total_files if total_files > 0 else 0,
            'average_additions_per_file': total_additions / total_files if total_files > 0 else 0,
            'average_deletions_per_file': total_deletions / total_files if total_files > 0 else 0,
            'content_analysis': content_analysis
        }
    
    def _generate_file_risk_assessment(self, repo_name: str, pr_number: int, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a risk assessment for a file using LLM
        
        Args:
            repo_name (str): Repository name
            pr_number (int): Pull request number
            file_info (Dict[str, Any]): File information
            
        Returns:
            Dict[str, Any]: Risk assessment data
        """
        if not self.openai_client:
            return {
                "file_path": file_info.get('filename', ''),
                "risk_score_file": 0,
                "high_risk_flag": False,
                "reasons": ["Risk assessment not available (OpenAI API key not configured)"],
                "confidence": 0.0
            }
        
        # Skip risk assessment for certain file types that might cause parsing issues
        file_path = file_info.get('filename', '')
        file_extension = file_info.get('file_extension', '').lower()
        
        # Skip for binary files, large files, or problematic file types
        file_size = file_info.get('size')
        if file_size is None or not isinstance(file_size, (int, float)):
            file_size = 0
        
        if (file_info.get('is_binary', False) or 
            file_size > 1000000 or  # Skip files larger than 1MB
            file_extension in ['exe', 'dll', 'so', 'dylib', 'bin', 'dat', 'db', 'sqlite']):
            return {
                "file_path": file_path,
                "risk_score_file": 0,
                "high_risk_flag": False,
                "reasons": [f"Skipped risk assessment for {file_extension} file type"],
                "confidence": 0.0
            }
        
        try:
            # Extract file metadata
            file_path = file_info.get('filename', '')
            language = file_info.get('language', 'Unknown')
            change_type = file_info.get('change_type', 'Unknown')
            lines_added = file_info.get('lines_added', 0)
            lines_deleted = file_info.get('lines_deleted', 0)
            lines_changed = file_info.get('lines_changed', 0)
            is_documentation = file_info.get('is_documentation', False)
            is_test_file = file_info.get('is_test_file', False)
            is_config_file = file_info.get('is_config_file', False)
            is_binary = file_info.get('is_binary', False)
            diff = file_info.get('patch', '')
            
            # Truncate diff if it's too large to prevent API issues
            if len(diff) > 8000:  # Limit diff to 8KB
                diff = diff[:8000] + "\n... (diff truncated for API limits)"
            
            # Count tests added/removed in this PR (simplified - would need PR context)
            tests_added_in_pr = 0  # This would need to be calculated from PR context
            tests_removed_in_pr = 0  # This would need to be calculated from PR context
            
            # Prepare the prompt for risk assessment
            prompt = f"""
System:
You are a meticulous code risk assessor. You score risk ONLY from the provided metadata and diff. 
Do not guess. If unsure, lower confidence.

User:
Return JSON ONLY with this schema:
{{
  "file_path": "string",
  "risk_score_file": 0,              // numeric 0–10
  "high_risk_flag": false,           // boolean threshold on risk_score_file
  "reasons": ["short, factual bullets"], // <=3 concise LLM bullets for transparency
  "confidence": 0.0                  // optional, helps decide if you trust LLM
}}

Scoring rules (additive, cap 10):
- Size: +0 (<=49 lines), +1 (50–199), +2 (200–599), +3 (>=600)
- Config/ENV/YAML/JSON/CI: +2
- Auth/ACL/PII/crypto/secrets: +2
- SQL/DDL schema change: +3 (+1 if non-BC e.g., DROP/RENAME/type shrink/not-null added)
- API surface change (public endpoint or exported signature): +3
- Guard/validation/try-catch removed or weakened: +2
- Error logging removed/disabled checks: +1
- Concurrency/locks/threads altered: +2
- New external side-effects (fs/network/process) without checks: +1
- Tests-only file in this PR: −2
- Tests added elsewhere covering this area: −1
- Tests removed in PR: +1
- Large symbol rewrite/refactor: +1
- Clear dead-code removal: −1

Hard guards before scoring:
- If documentation-only and <=50 lines changed -> score=0, high_risk=false.
- If binary/media file -> score=0, high_risk=false.
- If pure rename with no content delta -> score=0 or 1.

Hard high-risk floors (set score >= 8 and high_risk=true):
- Non-BC schema change
- Secrets/API keys introduced
- Auth/authz check removed

Set "reasons" as 2–4 concise facts tied to the diff. 
Set "confidence" lower (<=0.6) when the diff is too small/ambiguous or flags are uncertain.

Context:
repo: {repo_name}
pr_number: {pr_number}
file_path: {file_path}
language: {language}
change_type: {change_type}
lines_added: {lines_added}
lines_deleted: {lines_deleted}
lines_changed: {lines_changed}
is_documentation: {is_documentation}
is_test_file: {is_test_file}
is_config_file: {is_config_file}
is_binary: {is_binary}
tests_added_in_pr: {tests_added_in_pr}
tests_removed_in_pr: {tests_removed_in_pr}

DIFF (unified):
{diff}
"""
            
            # Call OpenAI API
            try:
                # Try newer OpenAI client first
                if hasattr(self.openai_client, 'chat'):
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a meticulous code risk assessor. Return only valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=500,
                        temperature=0.1
                    )
                    risk_assessment_text = response.choices[0].message.content.strip()
                else:
                    # Fallback to older openai library
                    response = self.openai_client.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a meticulous code risk assessor. Return only valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=500,
                        temperature=0.1
                    )
                    risk_assessment_text = response.choices[0].message.content.strip()
                
                # Parse JSON response with enhanced error handling
                try:
                    # Clean the response text - remove any markdown formatting
                    cleaned_text = risk_assessment_text.strip()
                    if cleaned_text.startswith('```json'):
                        cleaned_text = cleaned_text[7:]
                    if cleaned_text.endswith('```'):
                        cleaned_text = cleaned_text[:-3]
                    cleaned_text = cleaned_text.strip()
                    
                    risk_assessment = json.loads(cleaned_text)
                    
                    # Validate required fields
                    required_fields = ['file_path', 'risk_score_file', 'high_risk_flag', 'reasons']
                    for field in required_fields:
                        if field not in risk_assessment:
                            raise ValueError(f"Missing required field: {field}")
                    
                    return risk_assessment
                    
                except json.JSONDecodeError as json_error:
                    print(f"JSON parsing error for file {file_path}: {json_error}")
                    print(f"Raw response: {risk_assessment_text[:200]}...")
                    
                    # Try to extract JSON from the response using regex
                    import re
                    json_match = re.search(r'\{.*\}', risk_assessment_text, re.DOTALL)
                    if json_match:
                        try:
                            extracted_json = json_match.group(0)
                            risk_assessment = json.loads(extracted_json)
                            print(f"Successfully extracted JSON from response for {file_path}")
                            return risk_assessment
                        except json.JSONDecodeError:
                            pass
                    
                    return {
                        "file_path": file_path,
                        "risk_score_file": 0,
                        "high_risk_flag": False,
                        "reasons": [f"Error parsing risk assessment: {str(json_error)}"],
                        "confidence": 0.0
                    }
                    
            except Exception as api_error:
                print(f"OpenAI API error for file {file_path}: {api_error}")
                return {
                    "file_path": file_path,
                    "risk_score_file": 0,
                    "high_risk_flag": False,
                    "reasons": [f"Error calling OpenAI API: {str(api_error)}"],
                    "confidence": 0.0
                }
            
        except Exception as e:
            return {
                "file_path": file_info.get('filename', ''),
                "risk_score_file": 0,
                "high_risk_flag": False,
                "reasons": [f"Error generating risk assessment: {str(e)}"],
                "confidence": 0.0
            }
    
    def _calculate_pr_risk_assessment(self, files_info: List[Dict[str, Any]], file_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate PR-level risk assessment by aggregating file-level risk assessments
        
        Args:
            files_info (List[Dict[str, Any]]): List of file information with risk assessments
            file_stats (Dict[str, Any]): File statistics
            
        Returns:
            Dict[str, Any]: PR-level risk assessment
        """
        # Get files with valid risk assessments
        files_with_risk = [f for f in files_info if f.get('risk_assessment')]
        
        if not files_with_risk:
            return {
                'risk_score': 0,
                'risk_band': 'low',
                'high_risk': False,
                'risk_reasons': ['No file-level risk assessments available']
            }
        
        # Extract risk scores and reasons
        risk_scores = []
        all_reasons = []
        total_lines_changed = 0
        max_file_score = 0
        has_hard_condition = False
        net_tests_added = 0
        
        for file_info in files_with_risk:
            risk_assessment = file_info.get('risk_assessment', {})
            risk_score = risk_assessment.get('risk_score_file', 0)
            reasons = risk_assessment.get('reasons', [])
            lines_changed = file_info.get('lines_changed', 0)
            is_test_file = file_info.get('is_test_file', False)
            
            # Track metrics for PR-level calculation
            risk_scores.append(risk_score)
            all_reasons.extend(reasons)
            total_lines_changed += lines_changed
            max_file_score = max(max_file_score, risk_score)
            
            # Check for hard conditions (high-risk floors)
            if risk_score >= 8:
                has_hard_condition = True
            
            # Track test additions/removals
            if is_test_file:
                net_tests_added += file_info.get('additions', 0) - file_info.get('deletions', 0)
        
        # Calculate weighted average by change size
        weighted_sum = 0
        total_weight = 0
        
        for file_info in files_with_risk:
            risk_assessment = file_info.get('risk_assessment', {})
            risk_score = risk_assessment.get('risk_score_file', 0)
            lines_changed = file_info.get('lines_changed', 0)
            
            weighted_sum += risk_score * lines_changed
            total_weight += lines_changed
        
        # Calculate base PR risk score
        if total_weight > 0:
            pr_risk_score = weighted_sum / total_weight
        else:
            pr_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        
        # Apply PR-level rules
        # 1. Hard condition: If any file had a hard condition, force PR score to >= 8
        if has_hard_condition:
            pr_risk_score = max(pr_risk_score, 8.0)
        
        # 2. Max file score: If the maximum file score >= 8, bump PR score by +0.5 (capped at 10)
        if max_file_score >= 8:
            pr_risk_score = min(pr_risk_score + 0.5, 10.0)
        
        # 3. Tests added: If PR adds tests and no file >= 8, subtract 0.5 (floor at 0)
        if net_tests_added > 0 and max_file_score < 8:
            pr_risk_score = max(pr_risk_score - 0.5, 0.0)
        
        # Determine risk band
        if pr_risk_score <= 3.0:
            risk_band = 'low'
        elif pr_risk_score <= 6.9:
            risk_band = 'medium'
        else:
            risk_band = 'high'
        
        # Set high_risk flag
        high_risk = pr_risk_score >= 7.0
        
        # Create concise summary of risk reasons
        risk_reasons = self._summarize_risk_reasons(all_reasons)
        
        return {
            'risk_score': round(pr_risk_score, 2),
            'risk_band': risk_band,
            'high_risk': high_risk,
            'risk_reasons': risk_reasons,
            'calculation_details': {
                'weighted_average_score': round(weighted_sum / total_weight, 2) if total_weight > 0 else 0,
                'max_file_score': max_file_score,
                'has_hard_condition': has_hard_condition,
                'net_tests_added': net_tests_added,
                'total_files_with_risk_assessment': len(files_with_risk),
                'total_lines_changed': total_lines_changed
            }
        }
    
    def _summarize_risk_reasons(self, all_reasons: List[str]) -> List[str]:
        """
        Create a concise summary of risk reasons from file-level reasons
        
        Args:
            all_reasons (List[str]): List of all file-level risk reasons
            
        Returns:
            List[str]: Concise summary of risk reasons
        """
        if not all_reasons:
            return ['No specific risk reasons identified']
        
        # Count occurrences of common risk patterns
        reason_counts = {}
        for reason in all_reasons:
            # Normalize reason text for counting
            normalized = reason.lower().strip()
            reason_counts[normalized] = reason_counts.get(normalized, 0) + 1
        
        # Sort by frequency and take top reasons
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Create summary (limit to 3-4 most common reasons)
        summary_reasons = []
        for reason, count in sorted_reasons[:4]:
            if count > 1:
                summary_reasons.append(f"{reason} (in {count} files)")
            else:
                summary_reasons.append(reason)
        
        # If we have too many unique reasons, create a general summary
        if len(summary_reasons) > 4:
            summary_reasons = summary_reasons[:3]
            summary_reasons.append(f"Plus {len(all_reasons) - 3} other risk factors")
        
        return summary_reasons
    
    def _classify_pr_as_feature(self, pr: Dict[str, Any], detailed_pr: Dict[str, Any], files_info: List[Dict[str, Any]]) -> str:
        """
        Classify if a PR represents a feature based on labels and characteristics
        
        Args:
            pr (Dict[str, Any]): Raw PR data from GitHub API
            detailed_pr (Dict[str, Any]): Detailed PR information
            files_info (List[Dict[str, Any]]): File information for the PR
            
        Returns:
            str: Concise feature description or None if not a feature
        """
        # Define label buckets
        allow_labels = {
            'feature', 'enhancement', 'new-feature', 'type:feature', 
            'type:enhancement', 'improvement', 'addition', 'feat'
        }
        
        exclude_labels = {
            'bug', 'bugfix', 'fix', 'hotfix', 'regression', 'docs', 
            'documentation', 'refactor', 'cleanup', 'tech-debt', 
            'chore', 'maintenance', 'ci', 'build', 'infra', 'test', 
            'tests', 'qa', 'revert', 'security-fix', 'backport'
        }
        
        # Get PR labels
        labels = [label.get('name', '').lower() for label in pr.get('labels', [])]
        
        # Check if PR has any allow labels
        has_allow_label = any(label in allow_labels for label in labels)
        
        # Check if PR has any exclude labels
        has_exclude_label = any(label in exclude_labels for label in labels)
        
        # Check if PR is merged within selected window
        is_merged = pr.get('merged_at') is not None
        
        # Check if PR is unlabeled
        is_unlabeled = len(labels) == 0
        
        # Check if PR is documentation-only
        is_doc_only = self._is_documentation_only_pr(files_info)
        
        # Determine if PR is a feature
        is_feature = False
        
        if has_allow_label:
            # PR has explicit feature label
            is_feature = True
        elif is_merged and not has_exclude_label and not is_doc_only:
            # PR is merged, no exclude labels, not doc-only (unlabeled PRs are considered features)
            is_feature = True
        
        if not is_feature:
            return None
        
        # Generate concise feature description
        title = pr.get('title', '').strip()
        if title:
            # Use the PR title as the feature description
            return title
        
        # Fallback to a generic description
        return "Feature implementation"
    
    def _is_documentation_only_pr(self, files_info: List[Dict[str, Any]]) -> bool:
        """
        Check if a PR contains only documentation changes
        
        Args:
            files_info (List[Dict[str, Any]]): File information for the PR
            
        Returns:
            bool: True if PR contains only documentation files
        """
        if not files_info:
            return False
        
        # Check if all files are documentation files
        for file_info in files_info:
            if not self._is_documentation_file(file_info.get('filename', '')):
                return False
        
        return True
    
    def _extract_pr_metadata(self, pr: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
        """
        Extract required metadata from a pull request
        
        Args:
            pr (Dict[str, Any]): Raw PR data from GitHub API
            repo_name (str): Repository name for fetching detailed PR info
            
        Returns:
            Dict[str, Any]: Extracted metadata
        """
        # Helper function to safely get nested values
        def safe_get(data, *keys, default=None):
            """Safely get nested dictionary values"""
            try:
                for key in keys:
                    data = data[key]
                return data
            except (KeyError, TypeError, IndexError):
                return default
        
        # Helper function to safely get user info
        def safe_get_user(user_data):
            if not user_data:
                return {'login': None, 'id': None}
            return {
                'login': safe_get(user_data, 'login'),
                'id': safe_get(user_data, 'id')
            }
        
        # Get detailed PR information
        pr_number = safe_get(pr, 'number')
        if pr_number is None:
            print(f"Warning: PR number is None for PR data: {pr}")
            return {}
        
        detailed_pr = self._get_detailed_pr_info(repo_name, pr_number)
        
        # Handle case where detailed_pr is None
        if detailed_pr is None:
            detailed_pr = {}
        
        # Get repository information including repo_id
        repo_info = self._get_repo_info(repo_name)
        
        # Handle case where repo_info is None
        if repo_info is None:
            repo_info = {}
        
        # Get detailed file information
        files_info = self._get_pr_files(repo_name, pr_number)
        
        # Handle case where files_info is None
        if files_info is None:
            files_info = []
        
        # Fetch pre/post file contents for merged PRs
        if detailed_pr.get('merged_at'):
            try:
                enhanced_files_info = self._get_merged_pr_file_contents(repo_name, pr_number, files_info)
            except Exception as e:
                print(f"Error in _get_merged_pr_file_contents for PR #{pr_number}: {e}")
                enhanced_files_info = files_info
        else:
            enhanced_files_info = files_info
        
        # Calculate file statistics
        file_stats = self._calculate_file_statistics(enhanced_files_info)
        
        # Prepare complete PR data for summary generation
        complete_pr_data = {
            'pr_number': pr_number,
            'title': safe_get(pr, 'title', default=''),
            'body': safe_get(pr, 'body', default=''),
            'is_merged': safe_get(pr, 'merged_at') is not None,
            'files': enhanced_files_info,
            'additions': safe_get(detailed_pr, 'additions', default=0),
            'deletions': safe_get(detailed_pr, 'deletions', default=0),
            'changed_files': safe_get(detailed_pr, 'changed_files', default=0),
            'commits': safe_get(detailed_pr, 'commits', default=0),
            'comments': safe_get(detailed_pr, 'comments', default=0),
            'state': safe_get(pr, 'state', default='unknown')
        }
        
        # Generate PR-level summary
        pr_summary = self._generate_pr_summary(complete_pr_data)
        
        # Calculate PR-level risk assessment
        pr_risk_assessment = self._calculate_pr_risk_assessment(enhanced_files_info, file_stats)
        
        # Classify PR as feature
        feature_description = self._classify_pr_as_feature(pr, detailed_pr, enhanced_files_info)
        
        return {
            'pr_id': safe_get(pr, 'id'),
            'pr_number': pr_number,
            'repo_name': safe_get(pr, 'base', 'repo', 'full_name'),
            'repo_id': safe_get(repo_info, 'id'),
            'title': safe_get(pr, 'title', default=''),
            'body': safe_get(pr, 'body', default=''),
            'state': safe_get(pr, 'state', default='unknown'),
            'created_at': safe_get(pr, 'created_at'),
            'updated_at': safe_get(pr, 'updated_at'),
            'closed_at': safe_get(pr, 'closed_at'),
            'merged_at': safe_get(pr, 'merged_at'),
            'is_closed': safe_get(pr, 'state', default='') == 'closed',
            'is_merged': safe_get(pr, 'merged_at') is not None,
            'user': safe_get_user(safe_get(pr, 'user')),
            'assignees': [safe_get_user(assignee) for assignee in safe_get(pr, 'assignees', default=[])],
            'labels': [{'name': safe_get(label, 'name'), 'color': safe_get(label, 'color')} 
                      for label in safe_get(pr, 'labels', default=[])],
            'milestone': safe_get(pr, 'milestone', 'title') if safe_get(pr, 'milestone') else None,
            'comments': safe_get(detailed_pr, 'comments', default=0),
            'review_comments': safe_get(detailed_pr, 'review_comments', default=0),
            'commits': safe_get(detailed_pr, 'commits', default=0),
            'additions': safe_get(detailed_pr, 'additions', default=0),
            'deletions': safe_get(detailed_pr, 'deletions', default=0),
            'changed_files': safe_get(detailed_pr, 'changed_files', default=0),
            'base_branch': safe_get(pr, 'base', 'ref'),
            'head_branch': safe_get(pr, 'head', 'ref'),
            'draft': safe_get(pr, 'draft', default=False),
            'mergeable': safe_get(detailed_pr, 'mergeable'),
            'mergeable_state': safe_get(detailed_pr, 'mergeable_state'),
            'merged_by': safe_get(safe_get(detailed_pr, 'merged_by'), 'login') if safe_get(detailed_pr, 'merged_by') is not None else None,
            'merge_commit_sha': safe_get(detailed_pr, 'merge_commit_sha'),
            'requested_reviewers': [safe_get_user(reviewer) for reviewer in safe_get(pr, 'requested_reviewers', default=[])],
            'requested_teams': [{'name': safe_get(team, 'name'), 'id': safe_get(team, 'id')} 
                               for team in safe_get(pr, 'requested_teams', default=[])],
            'files': enhanced_files_info,
            'file_statistics': file_stats,
            'pr_summary': pr_summary,
            'pr_risk_assessment': pr_risk_assessment,
            'feature': feature_description
        }
    
    def save_pr_data(self, pr_data: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Save PR data to a JSON file
        
        Args:
            pr_data (List[Dict[str, Any]]): List of PR metadata
            filename (str): Optional filename, will generate one if not provided
            
        Returns:
            str: Path to the saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pr_data_{timestamp}.json"
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        # Create summary statistics
        summary = {
            'total_prs': len(pr_data),
            'open_prs': len([pr for pr in pr_data if not pr['is_closed']]),
            'closed_prs': len([pr for pr in pr_data if pr['is_closed']]),
            'merged_prs': len([pr for pr in pr_data if pr['is_merged']]),
            'draft_prs': len([pr for pr in pr_data if pr['draft']]),
            'collection_timestamp': datetime.now().isoformat(),
            'repo_name': pr_data[0]['repo_name'] if pr_data else None
        }
        
        # Add file statistics to summary
        if pr_data:
            total_files = sum(len(pr.get('files', [])) for pr in pr_data)
            total_file_additions = sum(pr.get('file_statistics', {}).get('total_additions', 0) for pr in pr_data)
            total_file_deletions = sum(pr.get('file_statistics', {}).get('total_deletions', 0) for pr in pr_data)
            total_file_changes = sum(pr.get('file_statistics', {}).get('total_changes', 0) for pr in pr_data)
            
            # Aggregate language statistics
            all_languages = {}
            for pr in pr_data:
                languages = pr.get('file_statistics', {}).get('languages', {})
                for lang, count in languages.items():
                    all_languages[lang] = all_languages.get(lang, 0) + count
            
            # Aggregate file type statistics
            all_file_types = {}
            for pr in pr_data:
                file_types = pr.get('file_statistics', {}).get('file_types', {})
                for file_type, count in file_types.items():
                    all_file_types[file_type] = all_file_types.get(file_type, 0) + count
            
            # Aggregate risk assessment statistics
            all_risk_scores = []
            total_high_risk_files = 0
            for pr in pr_data:
                risk_assessment = pr.get('file_statistics', {}).get('risk_assessment', {})
                if risk_assessment:
                    # Collect individual file risk scores
                    for file_info in pr.get('files', []):
                        if file_info.get('risk_assessment'):
                            score = file_info['risk_assessment'].get('risk_score_file', 0)
                            all_risk_scores.append(score)
                            if file_info['risk_assessment'].get('high_risk_flag', False):
                                total_high_risk_files += 1
            
            # Aggregate PR-level risk assessment statistics
            pr_risk_scores = []
            pr_risk_bands = {'low': 0, 'medium': 0, 'high': 0}
            total_high_risk_prs = 0
            all_pr_risk_reasons = []
            
            for pr in pr_data:
                pr_risk_assessment = pr.get('pr_risk_assessment', {})
                if pr_risk_assessment:
                    pr_score = pr_risk_assessment.get('risk_score', 0)
                    pr_band = pr_risk_assessment.get('risk_band', 'low')
                    pr_high_risk = pr_risk_assessment.get('high_risk', False)
                    pr_reasons = pr_risk_assessment.get('risk_reasons', [])
                    
                    pr_risk_scores.append(pr_score)
                    pr_risk_bands[pr_band] = pr_risk_bands.get(pr_band, 0) + 1
                    if pr_high_risk:
                        total_high_risk_prs += 1
                    all_pr_risk_reasons.extend(pr_reasons)
            
            # Aggregate feature statistics
            feature_prs = []
            non_feature_prs = []
            
            for pr in pr_data:
                feature_description = pr.get('feature')
                if feature_description:
                    feature_prs.append(feature_description)
                else:
                    non_feature_prs.append(pr.get('pr_number'))
            
            summary.update({
                'file_statistics': {
                    'total_files_changed': total_files,
                    'total_file_additions': total_file_additions,
                    'total_file_deletions': total_file_deletions,
                    'total_file_changes': total_file_changes,
                    'net_file_lines': total_file_additions - total_file_deletions,
                    'languages_distribution': all_languages,
                    'file_types_distribution': all_file_types,
                    'average_files_per_pr': total_files / len(pr_data) if pr_data else 0,
                    'average_changes_per_pr': total_file_changes / len(pr_data) if pr_data else 0
                },
                'risk_assessment_summary': {
                    'total_files_with_risk_assessment': len(all_risk_scores),
                    'total_high_risk_files': total_high_risk_files,
                    'average_risk_score': round(sum(all_risk_scores) / len(all_risk_scores), 2) if all_risk_scores else 0,
                    'max_risk_score': max(all_risk_scores) if all_risk_scores else 0,
                    'min_risk_score': min(all_risk_scores) if all_risk_scores else 0,
                    'risk_score_distribution': {
                        'low_risk_0_3': sum(1 for score in all_risk_scores if 0 <= score <= 3),
                        'medium_risk_4_6': sum(1 for score in all_risk_scores if 4 <= score <= 6),
                        'high_risk_7_10': sum(1 for score in all_risk_scores if 7 <= score <= 10)
                    }
                },
                'pr_risk_assessment_summary': {
                    'total_prs_with_risk_assessment': len(pr_risk_scores),
                    'total_high_risk_prs': total_high_risk_prs,
                    'average_pr_risk_score': round(sum(pr_risk_scores) / len(pr_risk_scores), 2) if pr_risk_scores else 0,
                    'max_pr_risk_score': max(pr_risk_scores) if pr_risk_scores else 0,
                    'min_pr_risk_score': min(pr_risk_scores) if pr_risk_scores else 0,
                    'pr_risk_band_distribution': pr_risk_bands,
                    'common_pr_risk_reasons': list(set(all_pr_risk_reasons))[:5]  # Top 5 unique reasons
                },
                'feature_summary': {
                    'total_feature_prs': len(feature_prs),
                    'total_non_feature_prs': len(non_feature_prs),
                    'feature_percentage': round(len(feature_prs) / len(pr_data) * 100, 2) if pr_data else 0,
                    'feature_descriptions': feature_prs[:10],  # Top 10 feature descriptions
                    'non_feature_pr_numbers': non_feature_prs[:10]  # Top 10 non-feature PR numbers
                }
            })
        
        output_data = {
            'summary': summary,
            'pull_requests': pr_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"PR data saved to: {filepath}")
        print(f"Summary: {summary}")
        
        return filepath

def main():
    parser = argparse.ArgumentParser(description='Collect pull request data from GitHub repository')
    parser.add_argument('repo', help='Repository name in format "owner/repo" (e.g., "microsoft/vscode")')
    parser.add_argument('--state', choices=['open', 'closed', 'all'], default='all',
                       help='Filter PRs by state (default: all)')
    parser.add_argument('--output', help='Output filename (optional)')
    
    args = parser.parse_args()
    
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable is required")
        print("Please set it using: export GITHUB_TOKEN=your_token_here")
        return
    
    try:
        # Initialize collector
        collector = GitHubPRCollector(github_token)
        
        # Fetch PR data
        pr_data = collector.get_repo_pull_requests(args.repo, args.state)
        
        if not pr_data:
            print("No pull requests found for the specified repository and state.")
            return
        
        # Save data to file
        output_file = collector.save_pr_data(pr_data, args.output)
        
        print(f"\nSuccessfully collected {len(pr_data)} pull requests from {args.repo}")
        print(f"Data saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 