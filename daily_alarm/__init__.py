from aws_cdk import (
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_lambda as _lambda,
)
from constructs import Construct


class DailyAlarmStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, environment: dict, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.eventbridge_daily_scheduled_event = events.Rule(
            self,
            "run_every_day",
            event_bus=None,  # "default" bus
            schedule=events.Schedule.cron(hour="23", minute="0"),
        )

        self.lambda_fn = _lambda.Function(
            self,
            "SillyLambda",
            function_name="silly-lambda",
            handler="index.handler",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.InlineCode(
                "def handler(event, context): print('event:', event)"
            ),
        )

        # connect AWS resources together
        self.eventbridge_daily_scheduled_event.add_target(
            events_targets.LambdaFunction(self.lambda_fn)
        )
        run_daily_expression = cloudwatch.MathExpression(
            expression="RUNNING_SUM(m)",  # check if Lambda runs 1 time per day
            # expression="RUNNING_SUM(m + IF(m < 1, 2, 0))",  # threshold=1
            # expression="IF(m > 1 OR m < 1, 1, 0)",  # threshold=0
            using_metrics={"m": self.lambda_fn.metric_invocations(statistic="sum")},
            period=Duration.hours(1),  # hard coded, check once per hour
        )
        self.daily_lambda_alarm = run_daily_expression.create_alarm(
            self,
            "DailyLambdaAlarm",
            alarm_name="daily-lambda-alarm",
            alarm_description="Watching for Lambda to run exactly once per day",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            threshold=1,
            datapoints_to_alarm=1,  # M variable in M out of N
            evaluation_periods=24,  # N variable in M out of N
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )
