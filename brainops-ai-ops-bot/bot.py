#!/usr/bin/env python3
"""
BrainOps AI Ops Bot - Main Entry Point
Multi-service DevOps automation and monitoring bot
"""

import sys
import asyncio
import signal
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.settings import Settings
from core.monitor import HealthMonitor
from core.alerts import AlertManager
from core.scheduler import JobScheduler
from api.app import create_app
from connectors import get_connector

console = Console()
settings = Settings()
monitor = HealthMonitor(settings)
alert_manager = AlertManager(settings)
scheduler = JobScheduler(settings)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug mode')
def cli(debug: bool):
    """BrainOps AI Ops Bot - DevOps Automation & Monitoring"""
    if debug:
        settings.debug_mode = True
        console.print("[yellow]Debug mode enabled[/yellow]")


@cli.command()
@click.option('--all', 'check_all', is_flag=True, help='Check all services')
@click.option('--service', help='Check specific service')
def health(check_all: bool, service: Optional[str]):
    """Check health status of integrated services"""
    
    services = settings.get_enabled_services() if check_all else [service] if service else []
    
    if not services:
        console.print("[red]No services specified. Use --all or --service <name>[/red]")
        return
    
    table = Table(title="Service Health Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Response Time", style="yellow")
    table.add_column("Details", style="white")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking services...", total=len(services))
        
        for service_name in services:
            progress.update(task, description=f"Checking {service_name}...")
            
            try:
                result = monitor.check_service(service_name)
                status = "✅ UP" if result['healthy'] else "❌ DOWN"
                response_time = f"{result.get('response_time', 'N/A')}ms"
                details = result.get('message', '')
                
                table.add_row(service_name, status, response_time, details)
                
                if not result['healthy']:
                    alert_manager.send_alert(
                        service=service_name,
                        severity='critical',
                        message=f"Service {service_name} is down: {details}"
                    )
                    
            except Exception as e:
                table.add_row(service_name, "❌ ERROR", "N/A", str(e))
                
            progress.advance(task)
    
    console.print(table)


@cli.command()
@click.option('--service', required=True, help='Service to deploy (render, vercel)')
@click.option('--app', required=True, help='Application/service name')
@click.option('--branch', default='main', help='Branch to deploy')
@click.option('--wait', is_flag=True, help='Wait for deployment to complete')
def deploy(service: str, app: str, branch: str, wait: bool):
    """Trigger deployment for a service"""
    
    console.print(f"[yellow]Deploying {app} to {service} from branch {branch}...[/yellow]")
    
    try:
        connector = get_connector(service, settings)
        
        with console.status(f"Triggering deployment..."):
            result = connector.deploy(app, branch)
        
        if result['success']:
            console.print(f"[green]✅ Deployment triggered successfully![/green]")
            console.print(f"Deployment ID: {result.get('deployment_id', 'N/A')}")
            
            if wait:
                console.print("[yellow]Waiting for deployment to complete...[/yellow]")
                # Implementation for waiting would go here
                
        else:
            console.print(f"[red]❌ Deployment failed: {result.get('error', 'Unknown error')}[/red]")
            alert_manager.send_alert(
                service=service,
                severity='error',
                message=f"Deployment failed for {app}: {result.get('error')}"
            )
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--service', required=True, help='Service to fetch logs from')
@click.option('--app', required=True, help='Application name')
@click.option('--lines', default=100, help='Number of log lines')
@click.option('--follow', is_flag=True, help='Follow log output')
def logs(service: str, app: str, lines: int, follow: bool):
    """Fetch logs from a service"""
    
    try:
        connector = get_connector(service, settings)
        
        if follow:
            console.print(f"[yellow]Following logs for {app} on {service}...[/yellow]")
            console.print("[dim]Press Ctrl+C to stop[/dim]\n")
            
            for log_line in connector.stream_logs(app):
                console.print(log_line, highlight=False)
        else:
            with console.status(f"Fetching logs..."):
                logs_data = connector.get_logs(app, lines)
            
            for log_line in logs_data:
                console.print(log_line, highlight=False)
                
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--service', required=True, help='Service to list resources from')
@click.option('--resource', required=True, help='Resource type (tasks, databases, etc.)')
@click.option('--format', 'output_format', default='table', type=click.Choice(['table', 'json']))
def list(service: str, resource: str, output_format: str):
    """List resources from a service"""
    
    try:
        connector = get_connector(service, settings)
        
        with console.status(f"Fetching {resource} from {service}..."):
            resources = connector.list_resources(resource)
        
        if output_format == 'json':
            console.print_json(data=resources)
        else:
            # Create table based on resource type
            table = Table(title=f"{service.capitalize()} {resource.capitalize()}")
            
            if resources:
                # Dynamic column creation based on first item
                for key in resources[0].keys():
                    table.add_column(key.replace('_', ' ').title())
                
                for item in resources:
                    table.add_row(*[str(v) for v in item.values()])
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--port', default=8000, help='Port to run the API server')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
def serve(port: int, host: str):
    """Start the API server"""
    
    console.print(f"[green]Starting BrainOps AI Ops Bot API on {host}:{port}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    
    app = create_app(settings)
    
    try:
        import uvicorn
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down API server[/yellow]")


@cli.command()
@click.option('--interval', default=5, help='Check interval in minutes')
@click.option('--services', help='Comma-separated list of services to monitor')
def schedule(interval: int, services: Optional[str]):
    """Run scheduled health checks"""
    
    service_list = services.split(',') if services else settings.get_enabled_services()
    
    console.print(f"[green]Starting scheduled health checks every {interval} minutes[/green]")
    console.print(f"Monitoring services: {', '.join(service_list)}")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    
    def health_check_job():
        console.print(f"\n[cyan]Running health check at {asyncio.get_event_loop().time()}[/cyan]")
        
        for service_name in service_list:
            try:
                result = monitor.check_service(service_name)
                if not result['healthy']:
                    alert_manager.send_alert(
                        service=service_name,
                        severity='error',
                        message=f"Health check failed for {service_name}"
                    )
            except Exception as e:
                console.print(f"[red]Error checking {service_name}: {e}[/red]")
    
    # Schedule the job
    scheduler.add_job(health_check_job, interval_minutes=interval)
    
    try:
        scheduler.start()
        # Keep the main thread alive
        signal.pause()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping scheduler[/yellow]")
        scheduler.stop()


@cli.command()
def test_alerts():
    """Test alert configuration"""
    
    console.print("[yellow]Testing alert channels...[/yellow]")
    
    # Test Slack
    if settings.enable_slack_alerts:
        console.print("Testing Slack alerts...")
        result = alert_manager.test_slack_alert()
        console.print(f"Slack: {'✅ Success' if result else '❌ Failed'}")
    
    # Test Email
    if settings.enable_email_alerts:
        console.print("Testing email alerts...")
        result = alert_manager.test_email_alert()
        console.print(f"Email: {'✅ Success' if result else '❌ Failed'}")
    
    console.print("\n[green]Alert test complete[/green]")


@cli.command()
def info():
    """Display bot configuration and status"""
    
    table = Table(title="BrainOps AI Ops Bot Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Version", "1.0.0")
    table.add_row("Debug Mode", str(settings.debug_mode))
    table.add_row("Log Level", settings.log_level)
    table.add_row("Timezone", settings.timezone)
    table.add_row("Enabled Services", ", ".join(settings.get_enabled_services()))
    table.add_row("Slack Alerts", "✅" if settings.enable_slack_alerts else "❌")
    table.add_row("Email Alerts", "✅" if settings.enable_email_alerts else "❌")
    table.add_row("Health Checks", "✅" if settings.enable_health_checks else "❌")
    
    console.print(table)


if __name__ == '__main__':
    cli()