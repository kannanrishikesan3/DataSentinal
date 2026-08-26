"""Report generation (JSON, CSV, HTML, text) and the remediation
recommendations engine. Recommendations are advisory only — they never
automatically modify or delete files.
"""

from datasentinel_agent.reporting.generator import build_report_data, generate_report
from datasentinel_agent.reporting.recommendations import recommend, recommend_for_file

__all__ = ["build_report_data", "generate_report", "recommend", "recommend_for_file"]
