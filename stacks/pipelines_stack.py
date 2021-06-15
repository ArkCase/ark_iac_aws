from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    core
)


class PipelinesStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repos = ['ark_base',
                 'ark_base_tomcat',
                 'ark_base_java',
                 'ark_snowbound',
                 'ark_activemq',
                 ]
        pipelines = {}

        # create ECR repos, with retain
        for repo in repos:
            ecr.Repository(self, f'ecr_{repo}',
                           repository_name=repo,
                           image_scan_on_push=True,
                           removal_policy=core.RemovalPolicy.DESTROY
                           )

        # create pipelines

        repo = 'ark_base'

        source_output = codepipeline.Artifact()

        # TODO TEMP: Create an S3 bucket
        bucket = s3.Bucket(self, "artifactsBucket",
                           removal_policy=core.RemovalPolicy.DESTROY)
        pipelinearkbaseArtifactsBucket = s3.Bucket(self, "pipelinearkbaseArtifactsBucket",
                                                   removal_policy=core.RemovalPolicy.DESTROY)

        pipelines['TODO'] = codepipeline.Pipeline(self, f'pipeline_{repo}',
                                                        stages=[
                                                            codepipeline.StageProps(stage_name="Source",
                                                                                    actions=[
                                                                                        codepipeline_actions.CodeStarConnectionsSourceAction(
                                                                                            connection_arn="arn:aws:codestar-connections:us-east-1:345280441424:connection/d9992729-173c-4f21-aa48-ba39a65198a3",
                                                                                            action_name="GitHub_Source",
                                                                                            owner="ArkCase",
                                                                                            repo=repo,
                                                                                            branch="main",
                                                                                            output=source_output)]),
                                                            #   codepipeline.StageProps(stage_name="Build",
                                                            #                           actions=[
                                                            #                               codepipeline_actions.CodeBuildAction(
                                                            #                                   action_name="UI_NG_Build",
                                                            #                                   project=ui_ng_build,
                                                            #                                   input=source_output,
                                                            #                                   outputs=[ui_ng_build_output])]),
                                                            codepipeline.StageProps(stage_name="Deploy",
                                                                                    actions=[
                                                                                        codepipeline_actions.S3DeployAction(
                                                                                            action_name="Deploy",
                                                                                            bucket=bucket,
                                                                                            input=source_output,  # TODO: ui_ng_build_output,
                                                                                            extract=True,
                                                                                            run_order=1
                                                                                        )])
                                                        ],
                                                  artifact_bucket=pipelinearkbaseArtifactsBucket
                                                  )

        core.CfnOutput(self, "EmptyBucketsCommand",
                       value=f"aws s3 rm s3://{bucket.bucket_name} --recursive --profile ark-cli-pipelines-stack && aws s3 rm s3://{pipelinearkbaseArtifactsBucket.bucket_name} --recursive --profile ark-cli-pipelines-stack")
