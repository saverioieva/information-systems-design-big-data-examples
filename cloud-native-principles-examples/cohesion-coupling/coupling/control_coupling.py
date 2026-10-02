"""Control coupling: one module passes flags that decide another module's behavior."""


class ReportModule:
    def generate(self, data: list[int], detailed: bool) -> str:
        if detailed:
            return f"detailed report: count={len(data)}, values={data}"
        return f"summary report: count={len(data)}"


class DashboardModule:
    def __init__(self, reports: ReportModule):
        self.reports = reports

    def build_report(self) -> str:
        # The flag tells ReportModule which control path to execute.
        return self.reports.generate([10, 20, 30], detailed=True)


def demo() -> list[str]:
    return [
        DashboardModule(ReportModule()).build_report(),
        "Observe: Module A passes a control flag that selects Module B's behavior.",
    ]
