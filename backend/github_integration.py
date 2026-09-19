"""
GitHub Integration Engine.
Automatically files structured bug reports into a specified GitHub repository
when high-severity issues or crashes are detected.
"""

import logging
from typing import List, Optional
import httpx

from backend.config import settings
from backend.schemas import BugReport, FindingSeverity

logger = logging.getLogger("autonomous_tester.github")


class GitHubIntegration:
    """Handles automatic bug filing to GitHub Issues."""

    def __init__(self, token: Optional[str] = None, repo: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.repo = repo or settings.GITHUB_REPO
        self.enabled = bool(self.token and self.repo)
        
        if not self.enabled:
            logger.info("GitHub Integration is disabled (missing GITHUB_TOKEN or GITHUB_REPO).")
        else:
            logger.info(f"GitHub Integration enabled for repository: {self.repo}")

    async def file_bug(self, bug: BugReport) -> Optional[str]:
        """
        File a single bug report to GitHub Issues.
        Returns the issue URL if successful.
        """
        if not self.enabled:
            return None

        url = f"https://api.github.com/repos/{self.repo}/issues"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Format the issue body using Markdown
        body_parts = [
            f"## {bug.description}",
            "",
            "### Details",
            f"- **Severity:** {bug.severity.value}",
            f"- **Category:** {bug.category.value}",
            f"- **URL:** {bug.url or 'N/A'}",
            f"- **Step:** {bug.step_number or 'N/A'}",
            "",
            "### Expected Behavior",
            bug.expected_behavior,
            "",
            "### Actual Behavior",
            bug.actual_behavior,
            "",
            "### Reproduction Steps",
        ]
        
        for i, step in enumerate(bug.reproduction_steps, 1):
            body_parts.append(f"{i}. {step}")
            
        if bug.console_errors:
            body_parts.append("")
            body_parts.append("### Console Errors")
            body_parts.append("```javascript")
            for err in bug.console_errors[:3]:  # Limit to first 3 to avoid massive issues
                body_parts.append(err[:500])
            body_parts.append("```")
            
        if bug.network_errors:
            body_parts.append("")
            body_parts.append("### Network Errors")
            body_parts.append("```http")
            for err in bug.network_errors[:3]:
                body_parts.append(err[:200])
            body_parts.append("```")
            
        body_parts.extend([
            "",
            "### AI Suggested Fix",
            f"> {bug.suggested_fix}",
            "",
            "---",
            "*Report generated automatically by Autonomous QA Agent.*"
        ])

        labels = ["bug", "automated-qa", f"severity:{bug.severity.value.lower()}", bug.category.value.lower()]

        payload = {
            "title": f"[{bug.bug_id}] {bug.title}",
            "body": "\n".join(body_parts),
            "labels": labels,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 201:
                    issue_data = response.json()
                    issue_url = issue_data.get("html_url")
                    logger.info(f"Successfully filed GitHub Issue: {issue_url}")
                    return issue_url
                else:
                    logger.error(f"Failed to file GitHub Issue. Status: {response.status_code}. Response: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error communicating with GitHub API: {e}")
            return None

    async def file_critical_bugs(self, bugs: List[BugReport]) -> List[str]:
        """
        File only High or Critical severity bugs to avoid spam.
        """
        if not self.enabled:
            return []
            
        filed_urls = []
        for bug in bugs:
            if bug.severity in [FindingSeverity.HIGH, FindingSeverity.CRITICAL]:
                url = await self.file_bug(bug)
                if url:
                    filed_urls.append(url)
                    
        return filed_urls
