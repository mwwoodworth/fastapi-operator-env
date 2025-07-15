"""
GitHub connector for repository management and CI/CD integration
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from github import Github, GithubException
from .base import BaseConnector


logger = logging.getLogger(__name__)


class GitHubConnector(BaseConnector):
    """GitHub API connector"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config.get('token')
        self.repos = config.get('repos', [])
        self.client = None
        self._user = None
    
    def authenticate(self) -> bool:
        """Initialize GitHub client"""
        try:
            self.client = Github(self.token)
            # Test authentication by getting user info
            self._user = self.client.get_user()
            _ = self._user.login  # This will trigger auth check
            
            self._is_authenticated = True
            logger.info(f"GitHub authentication successful as {self._user.login}")
            return True
            
        except GithubException as e:
            logger.error(f"GitHub authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"GitHub authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check GitHub API health"""
        try:
            # Check rate limit as health indicator
            rate_limit = self.client.get_rate_limit()
            core_limit = rate_limit.core
            
            # Check if we can access configured repos
            accessible_repos = 0
            for repo_name in self.repos:
                try:
                    self.client.get_repo(repo_name)
                    accessible_repos += 1
                except:
                    pass
            
            return {
                'healthy': True,
                'message': f"API healthy, {core_limit.remaining}/{core_limit.limit} requests remaining",
                'details': {
                    'rate_limit_remaining': core_limit.remaining,
                    'rate_limit_total': core_limit.limit,
                    'rate_limit_reset': core_limit.reset.isoformat(),
                    'configured_repos': len(self.repos),
                    'accessible_repos': accessible_repos
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List GitHub resources"""
        if resource_type == 'repos':
            return self.list_repos()
        elif resource_type == 'issues':
            return self.list_issues()
        elif resource_type == 'pulls':
            return self.list_pull_requests()
        elif resource_type == 'workflows':
            return self.list_workflows()
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_repos(self) -> List[Dict[str, Any]]:
        """List accessible repositories"""
        try:
            repos = []
            
            # List configured repos
            for repo_name in self.repos:
                try:
                    repo = self.client.get_repo(repo_name)
                    repos.append({
                        'name': repo.name,
                        'full_name': repo.full_name,
                        'description': repo.description,
                        'private': repo.private,
                        'stars': repo.stargazers_count,
                        'forks': repo.forks_count,
                        'open_issues': repo.open_issues_count,
                        'default_branch': repo.default_branch,
                        'last_push': repo.pushed_at.isoformat() if repo.pushed_at else None
                    })
                except Exception as e:
                    logger.error(f"Cannot access repo {repo_name}: {e}")
            
            return repos
            
        except Exception as e:
            logger.error(f"Error listing repos: {e}")
            return []
    
    def list_issues(self, repo_name: Optional[str] = None, 
                   state: str = 'open') -> List[Dict[str, Any]]:
        """List issues from repositories"""
        try:
            issues = []
            
            repos_to_check = [repo_name] if repo_name else self.repos
            
            for repo_name in repos_to_check:
                try:
                    repo = self.client.get_repo(repo_name)
                    repo_issues = repo.get_issues(state=state)
                    
                    for issue in repo_issues:
                        # Skip pull requests
                        if not issue.pull_request:
                            issues.append({
                                'number': issue.number,
                                'title': issue.title,
                                'state': issue.state,
                                'author': issue.user.login,
                                'assignees': [a.login for a in issue.assignees],
                                'labels': [l.name for l in issue.labels],
                                'created_at': issue.created_at.isoformat(),
                                'updated_at': issue.updated_at.isoformat(),
                                'repo': repo_name
                            })
                except Exception as e:
                    logger.error(f"Error getting issues from {repo_name}: {e}")
            
            return issues
            
        except Exception as e:
            logger.error(f"Error listing issues: {e}")
            return []
    
    def list_pull_requests(self, repo_name: Optional[str] = None, 
                          state: str = 'open') -> List[Dict[str, Any]]:
        """List pull requests from repositories"""
        try:
            prs = []
            
            repos_to_check = [repo_name] if repo_name else self.repos
            
            for repo_name in repos_to_check:
                try:
                    repo = self.client.get_repo(repo_name)
                    pulls = repo.get_pulls(state=state)
                    
                    for pr in pulls:
                        prs.append({
                            'number': pr.number,
                            'title': pr.title,
                            'state': pr.state,
                            'author': pr.user.login,
                            'base': pr.base.ref,
                            'head': pr.head.ref,
                            'mergeable': pr.mergeable,
                            'created_at': pr.created_at.isoformat(),
                            'updated_at': pr.updated_at.isoformat(),
                            'repo': repo_name
                        })
                except Exception as e:
                    logger.error(f"Error getting PRs from {repo_name}: {e}")
            
            return prs
            
        except Exception as e:
            logger.error(f"Error listing pull requests: {e}")
            return []
    
    def list_workflows(self, repo_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List GitHub Actions workflows"""
        try:
            workflows = []
            
            repos_to_check = [repo_name] if repo_name else self.repos
            
            for repo_name in repos_to_check:
                try:
                    repo = self.client.get_repo(repo_name)
                    repo_workflows = repo.get_workflows()
                    
                    for workflow in repo_workflows:
                        workflows.append({
                            'id': workflow.id,
                            'name': workflow.name,
                            'state': workflow.state,
                            'path': workflow.path,
                            'created_at': workflow.created_at.isoformat(),
                            'updated_at': workflow.updated_at.isoformat(),
                            'repo': repo_name
                        })
                except Exception as e:
                    logger.error(f"Error getting workflows from {repo_name}: {e}")
            
            return workflows
            
        except Exception as e:
            logger.error(f"Error listing workflows: {e}")
            return []
    
    def deploy(self, app_name: str, branch: str = 'main') -> Dict[str, Any]:
        """Trigger deployment via GitHub Actions"""
        try:
            # Parse repo name from app_name
            if '/' in app_name:
                repo_name = app_name
            else:
                # Try to find repo containing app_name
                repo_name = None
                for repo in self.repos:
                    if app_name in repo:
                        repo_name = repo
                        break
                
                if not repo_name:
                    return {
                        'success': False,
                        'error': f"Cannot find repository for app: {app_name}"
                    }
            
            repo = self.client.get_repo(repo_name)
            
            # Trigger workflow dispatch event
            # Look for a deployment workflow
            workflows = repo.get_workflows()
            deploy_workflow = None
            
            for workflow in workflows:
                if 'deploy' in workflow.name.lower():
                    deploy_workflow = workflow
                    break
            
            if deploy_workflow:
                # Create workflow dispatch event
                result = repo.create_repository_dispatch(
                    event_type='deploy',
                    client_payload={'branch': branch}
                )
                
                return {
                    'success': True,
                    'deployment_id': f"workflow_dispatch_{datetime.utcnow().timestamp()}",
                    'workflow': deploy_workflow.name
                }
            else:
                return {
                    'success': False,
                    'error': "No deployment workflow found"
                }
                
        except Exception as e:
            logger.error(f"Error triggering deployment: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_logs(self, app_name: str, lines: int = 100) -> List[str]:
        """Get workflow logs"""
        try:
            # Parse repo name
            if '/' in app_name:
                repo_name = app_name
            else:
                # Find matching repo
                repo_name = None
                for repo in self.repos:
                    if app_name in repo:
                        repo_name = repo
                        break
                
                if not repo_name:
                    return [f"Cannot find repository for app: {app_name}"]
            
            repo = self.client.get_repo(repo_name)
            
            # Get recent workflow runs
            runs = repo.get_workflow_runs()
            logs = []
            
            if runs.totalCount > 0:
                latest_run = runs[0]
                logs.append(f"Latest workflow run: {latest_run.name}")
                logs.append(f"Status: {latest_run.status}")
                logs.append(f"Conclusion: {latest_run.conclusion}")
                logs.append(f"Started: {latest_run.created_at}")
                logs.append(f"URL: {latest_run.html_url}")
                
                # Get job details
                jobs = latest_run.jobs()
                for job in jobs:
                    logs.append(f"\nJob: {job.name}")
                    logs.append(f"  Status: {job.status}")
                    logs.append(f"  Started: {job.started_at}")
                    logs.append(f"  Completed: {job.completed_at}")
            else:
                logs.append("No workflow runs found")
            
            return logs[:lines]
            
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return [f"Error getting logs: {str(e)}"]
    
    def create_resource(self, resource_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a GitHub resource"""
        if resource_type == 'issue':
            return self.create_issue(data)
        elif resource_type == 'pr':
            return self.create_pull_request(data)
        else:
            raise ValueError(f"Cannot create resource type: {resource_type}")
    
    def create_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new issue"""
        try:
            repo_name = issue_data.pop('repo')
            repo = self.client.get_repo(repo_name)
            
            issue = repo.create_issue(
                title=issue_data.get('title'),
                body=issue_data.get('body', ''),
                assignees=issue_data.get('assignees', []),
                labels=issue_data.get('labels', [])
            )
            
            return {
                'success': True,
                'issue_number': issue.number,
                'url': issue.html_url
            }
            
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_commit_history(self, repo_name: str, branch: str = None, 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent commits"""
        try:
            repo = self.client.get_repo(repo_name)
            commits = repo.get_commits(sha=branch)[:limit] if branch else repo.get_commits()[:limit]
            
            commit_list = []
            for commit in commits:
                commit_list.append({
                    'sha': commit.sha[:7],
                    'message': commit.commit.message.split('\n')[0],
                    'author': commit.commit.author.name,
                    'date': commit.commit.author.date.isoformat()
                })
            
            return commit_list
            
        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            return []