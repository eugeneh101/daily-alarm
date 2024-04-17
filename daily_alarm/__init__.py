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
            "RunEveryDay",
            rule_name="run-every-day",
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
        self.lambda_under_invoked_alarm = cloudwatch.Alarm(
            self,
            "LambdaUnderInvokedAlarm",
            alarm_name="lambda-under-invoked-alarm",
            metric=self.lambda_fn.metric_invocations(
                statistic="sum", period=Duration.hours(1)
            ),
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
            threshold=1,
            datapoints_to_alarm=24,  # M variable in M out of N
            evaluation_periods=24,  # N variable in M out of N
        )
        run_daily_expression = cloudwatch.MathExpression(
            expression="FILL(m, 0)",  # fill MISSING data
            using_metrics={
                "m": self.lambda_fn.metric_invocations(statistic="sum"),
            },
            period=Duration.hours(24),
        )
        self.lambda_over_invoked_alarm = run_daily_expression.create_alarm(
            self,
            "LambdaUnderOverAlarm",
            alarm_name="lambda-over-invoked-alarm",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
            threshold=1,
            evaluation_periods=1,
        )
        alarm_rule = cloudwatch.AlarmRule.any_of(
            self.lambda_under_invoked_alarm, self.lambda_over_invoked_alarm
        )
        self.daily_lambda_composite_alarm = cloudwatch.CompositeAlarm(
            self,
            "DailyLambdaCompositeAlarm",
            composite_alarm_name="daily-lambda-composite-alarm",
            alarm_rule=alarm_rule,
            alarm_description="Watching for Lambda to run exactly once per day",
            # actions_enabled=None, actions_suppressor=None, actions_suppressor_extension_period=None, actions_suppressor_wait_period=None,
        )
        run_daily_expression = cloudwatch.MathExpression(
            expression=(
                "IF(FILL(m, 0) == 1, 0, 1)"  # check if Lambda runs 1 time per day
                "+ e"  # without any errors
            ),
            using_metrics={
                "m": self.lambda_fn.metric_invocations(statistic="sum"),
                "e": self.lambda_fn.metric_errors(statistic="sum"),
            },
            period=Duration.hours(24),
        )
        self.daily_lambda_with_error_alarm = run_daily_expression.create_alarm(
            self,
            "DailyLambdaWithErrorAlarm",
            alarm_name="daily-lambda-with-error-alarm",
            alarm_description="Watching for Lambda to run exactly once per day",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            threshold=0,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,  # used FILL to avoid dealing with MISSING
        )
