"""
Weekly report generation task for BrainOps.

This task aggregates data from multiple sources to generate comprehensive
weekly reports for different business verticals, using AI agents to
analyze trends and create insights.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from apps.backend.tasks.base import BaseTask
from apps.backend.agents.claude_agent import ClaudeAgent
from apps.backend.agents.gemini_agent import GeminiAgent
from apps.backend.memory.memory_store import MemoryStore
from apps.backend.integrations.clickup import ClickUpIntegration
from apps.backend.core.logging import logger


class GenerateWeeklyReportTask(BaseTask):
    """
    Generates comprehensive weekly reports for specified business verticals.
    
    Aggregates data from ClickUp, memory system, and task executions to
    create AI-powered insights and recommendations for the week ahead.
    """
    
    TASK_ID = "generate_weekly_report"
    DESCRIPTION = "Generate AI-powered weekly business report with insights"
    
    def __init__(self):
        super().__init__()
        self.claude = ClaudeAgent()
        self.gemini = GeminiAgent()
        self.memory_store = MemoryStore()
        self.clickup = ClickUpIntegration()
        
    async def run(
        self,
        vertical: str = "all",  # all, roofing, automation, project_management, passive_income
        include_metrics: bool = True,
        include_recommendations: bool = True,
        send_to_slack: bool = False
    ) -> Dict[str, Any]:
        """
        Generate weekly report for specified business vertical.
        
        Args:
            vertical: Which business vertical to report on
            include_metrics: Whether to include performance metrics
            include_recommendations: Whether to include AI recommendations
            send_to_slack: Whether to post report to Slack
            
        Returns:
            Generated report with insights and optional recommendations
        """
        # Define report period (last 7 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        logger.info(f"Generating weekly report for vertical: {vertical}")
        
        # Gather data from various sources
        report_data = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "vertical": vertical,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Collect metrics if requested
        if include_metrics:
            report_data["metrics"] = await self._gather_metrics(vertical, start_date, end_date)
        
        # Gather activity data
        report_data["activities"] = await self._gather_activities(vertical, start_date, end_date)
        
        # Generate AI analysis of the data
        analysis = await self._generate_analysis(report_data)
        report_data["analysis"] = analysis
        
        # Generate recommendations if requested
        if include_recommendations:
            recommendations = await self._generate_recommendations(report_data)
            report_data["recommendations"] = recommendations
        
        # Format the final report
        formatted_report = await self._format_report(report_data)
        
        # Store report in memory system
        await self.memory_store.add_system_knowledge(
            content=formatted_report["text_version"],
            metadata={
                "report_type": "weekly",
                "vertical": vertical,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "report_data": report_data
            }
        )
        
        # Send to Slack if requested
        if send_to_slack:
            await self._send_to_slack(formatted_report)
        
        return {
            "report": formatted_report,
            "data": report_data,
            "status": "completed"
        }
    
    async def _gather_metrics(
        self, 
        vertical: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Gather performance metrics for the specified period.
        
        Collects task completion rates, revenue indicators, and
        engagement metrics from various systems.
        """
        metrics = {
            "task_metrics": {},
            "engagement_metrics": {},
            "revenue_indicators": {}
        }
        
        # Get task execution metrics from database
        task_stats = await self.memory_store.get_task_statistics(
            start_date=start_date,
            end_date=end_date,
            vertical=vertical if vertical != "all" else None
        )
        
        metrics["task_metrics"] = {
            "total_executions": task_stats.get("total", 0),
            "successful_executions": task_stats.get("successful", 0),
            "failed_executions": task_stats.get("failed", 0),
            "success_rate": task_stats.get("success_rate", 0),
            "average_execution_time_ms": task_stats.get("avg_execution_time", 0)
        }
        
        # Get ClickUp task completion metrics
        clickup_tasks = await self.clickup.get_tasks_completed_in_period(
            start_date=start_date,
            end_date=end_date
        )
        
        metrics["task_metrics"]["clickup_tasks_completed"] = len(clickup_tasks)
        
        # Calculate engagement metrics based on memory entries
        memory_stats = await self.memory_store.get_memory_statistics(
            start_date=start_date,
            end_date=end_date
        )
        
        metrics["engagement_metrics"] = {
            "knowledge_entries_added": memory_stats.get("entries_added", 0),
            "conversations_logged": memory_stats.get("conversations", 0),
            "documents_processed": memory_stats.get("documents", 0)
        }
        
        return metrics
    
    async def _gather_activities(
        self, 
        vertical: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Gather significant activities from the period.
        
        Collects completed tasks, important conversations, and
        system events for the report.
        """
        activities = []
        
        # Get completed tasks from ClickUp
        completed_tasks = await self.clickup.get_tasks_completed_in_period(
            start_date=start_date,
            end_date=end_date
        )
        
        for task in completed_tasks[:10]:  # Limit to top 10
            activities.append({
                "type": "task_completed",
                "title": task["name"],
                "date": task["date_closed"],
                "source": "clickup",
                "metadata": {
                    "status": task["status"]["status"],
                    "assignees": [a["username"] for a in task.get("assignees", [])]
                }
            })
        
        # Get significant memory entries
        significant_memories = await self.memory_store.get_important_memories(
            start_date=start_date,
            end_date=end_date,
            min_importance=7
        )
        
        for memory in significant_memories[:5]:  # Limit to top 5
            activities.append({
                "type": "knowledge_added",
                "title": memory["content"][:100] + "...",
                "date": memory["created_at"],
                "source": "memory",
                "metadata": memory.get("metadata", {})
            })
        
        # Sort activities by date
        activities.sort(key=lambda x: x["date"], reverse=True)
        
        return activities
    
    async def _generate_analysis(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to analyze the gathered data and generate insights.
        
        Claude provides the main analysis while Gemini adds SEO/content insights.
        """
        # Prepare context for Claude
        analysis_prompt = f"""
        Analyze this weekly business report data and provide insights:
        
        Vertical: {report_data['vertical']}
        Period: {report_data['period']['start']} to {report_data['period']['end']}
        
        Metrics:
        {json.dumps(report_data.get('metrics', {}), indent=2)}
        
        Key Activities:
        {json.dumps(report_data.get('activities', [])[:5], indent=2)}
        
        Provide:
        1. Key performance highlights
        2. Areas of concern
        3. Trends observed
        4. Comparison to typical performance (if known)
        
        Keep analysis concise and actionable.
        """
        
        # Get analysis from Claude
        claude_analysis = await self.claude.analyze_text(
            text=analysis_prompt,
            analysis_type="business_performance"
        )
        
        # Get content/SEO insights from Gemini if relevant
        gemini_insights = None
        if report_data['vertical'] in ['passive_income', 'all']:
            gemini_insights = await self.gemini.generate_content_insights(
                topic="Weekly performance in content and digital products",
                context=report_data.get('metrics', {})
            )
        
        return {
            "performance_analysis": claude_analysis,
            "content_insights": gemini_insights,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def _generate_recommendations(self, report_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generate AI-powered recommendations based on the analysis.
        
        Creates actionable recommendations for the week ahead.
        """
        # Prepare context for recommendations
        rec_prompt = f"""
        Based on this weekly report analysis, provide 3-5 specific recommendations:
        
        Analysis:
        {json.dumps(report_data.get('analysis', {}), indent=2)}
        
        Metrics:
        {json.dumps(report_data.get('metrics', {}), indent=2)}
        
        Provide actionable recommendations that:
        1. Address any performance issues
        2. Capitalize on positive trends
        3. Suggest specific tasks or focus areas
        4. Include measurable outcomes where possible
        
        Format as a list of recommendations with title and description.
        """
        
        # Get recommendations from Claude
        recommendations_text = await self.claude.generate_text(
            prompt=rec_prompt,
            max_tokens=1000
        )
        
        # Parse recommendations into structured format
        recommendations = []
        lines = recommendations_text.strip().split('\n')
        current_rec = {}
        
        for line in lines:
            if line.startswith('**') or line.startswith('###'):
                if current_rec:
                    recommendations.append(current_rec)
                current_rec = {
                    "title": line.strip('*#').strip(),
                    "description": ""
                }
            elif current_rec:
                current_rec["description"] += line.strip() + " "
        
        if current_rec:
            recommendations.append(current_rec)
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    async def _format_report(self, report_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Format the report data into readable text and HTML versions.
        
        Creates both plain text (for Slack) and HTML (for web/email) versions.
        """
        # Create text version
        text_lines = [
            f"📊 Weekly Report: {report_data['vertical'].title()}",
            f"Period: {report_data['period']['start'][:10]} to {report_data['period']['end'][:10]}",
            "",
            "## Key Metrics",
        ]
        
        if "metrics" in report_data:
            metrics = report_data["metrics"]
            if "task_metrics" in metrics:
                text_lines.extend([
                    f"- Tasks Executed: {metrics['task_metrics']['total_executions']}",
                    f"- Success Rate: {metrics['task_metrics']['success_rate']:.1f}%",
                    f"- ClickUp Tasks Completed: {metrics['task_metrics']['clickup_tasks_completed']}",
                ])
            
            if "engagement_metrics" in metrics:
                text_lines.extend([
                    f"- Knowledge Entries: {metrics['engagement_metrics']['knowledge_entries_added']}",
                    f"- Documents Processed: {metrics['engagement_metrics']['documents_processed']}",
                ])
        
        text_lines.extend(["", "## Analysis"])
        
        if "analysis" in report_data and report_data["analysis"]["performance_analysis"]:
            text_lines.append(report_data["analysis"]["performance_analysis"])
        
        if "recommendations" in report_data:
            text_lines.extend(["", "## Recommendations"])
            for i, rec in enumerate(report_data["recommendations"], 1):
                text_lines.extend([
                    f"{i}. **{rec['title']}**",
                    f"   {rec['description']}",
                ])
        
        text_version = "\n".join(text_lines)
        
        # Create HTML version (simplified for this example)
        html_version = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h1>Weekly Report: {report_data['vertical'].title()}</h1>
            <p>Period: {report_data['period']['start'][:10]} to {report_data['period']['end'][:10]}</p>
            
            <h2>Key Metrics</h2>
            <ul>
                {"".join(f"<li>{line[2:]}</li>" for line in text_lines if line.startswith("- "))}
            </ul>
            
            <h2>Analysis</h2>
            <p>{report_data.get('analysis', {}).get('performance_analysis', '')}</p>
            
            {"<h2>Recommendations</h2>" + "".join(f"<h3>{r['title']}</h3><p>{r['description']}</p>" for r in report_data.get('recommendations', [])) if 'recommendations' in report_data else ""}
        </body>
        </html>
        """
        
        return {
            "text_version": text_version,
            "html_version": html_version
        }
    
    async def _send_to_slack(self, formatted_report: Dict[str, str]):
        """Send formatted report to designated Slack channel."""
        # This would integrate with the Slack integration
        # For now, just log that we would send it
        logger.info("Would send weekly report to Slack")
        # In practice: await self.slack.post_message(channel="#reports", text=formatted_report["text_version"])