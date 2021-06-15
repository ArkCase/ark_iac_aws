#!/usr/bin/env python3

from aws_cdk import core

from stacks.iam_stack import IamStack
from stacks.pipelines_stack import PipelinesStack


app = core.App()
IamStack(app, "iam-stack")
PipelinesStack(app, "pipelines-stack")

app.synth()
