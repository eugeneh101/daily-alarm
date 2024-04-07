import aws_cdk as cdk

from daily_alarm import DailyAlarmStack


app = cdk.App()
environment = app.node.try_get_context("environment")

DailyAlarmStack(
    app,
    "DailyAlarmStack",
    environment=environment,
    env=cdk.Environment(region=environment["AWS_REGION"]),
)
app.synth()
