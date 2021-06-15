import json
import pytest

from aws_cdk import core
from stacks.ark_iac_aws_stack import ArkIacAwsStack


def get_template():
    app = core.App()
    ArkIacAwsStack(app, "ark-iac-aws")
    return json.dumps(app.synth().get_stack("ark-iac-aws").template)


def test_sqs_queue_created():
    assert("AWS::SQS::Queue" in get_template())


def test_sns_topic_created():
    assert("AWS::SNS::Topic" in get_template())
