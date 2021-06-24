from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
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
        ecr_repos = {}

        sns_topic = sns.Topic(self, "docker_image_build_sns_topic",
                              display_name="ArkCase Docker Image Build Pipeline notifications")
        sns_topic.add_subscription(sns_subscriptions.EmailSubscription('jon.holman@armedia.com'))

        pipelinearkbaseArtifactsBucket = s3.Bucket(self, "pipelinearkbaseArtifactsBucket")

        docker_image_build = codebuild.PipelineProject(self, "docker_image_build",
                                                       build_spec=codebuild.BuildSpec.from_object({
                                                           'version': "0.2",
                                                           'phases': {
                                                               'build': {
                                                                   'commands': [
                                                                       "echo Logging in to Amazon ECR...",
                                                                       f"$(aws ecr get-login --no-include-email --region {core.Aws.REGION})",

                                                                       "echo $RepositoryName",
                                                                       "echo $FullCommitId",
                                                                       "repoName=$(echo $RepositoryName | cut -d/ -f2)",
                                                                       "commitId=$(echo $FullCommitId | cut -c1-7)",
                                                                       "dateStamp=$(date +%Y%m%d)",
                                                                       "echo Repo Name: $repoName",
                                                                       "echo Repo Name: $commitId",
                                                                       "ls",
                                                                       "existingTags=$(aws ecr list-images --repository-name $repoName --output json --query 'imageIds[*].imageTag')",
                                                                       "echo Tags that already exist in this ECR repo: $existingTags"


                                                                       # TODO: Unit tests
                                                                       # TODO: Static Analysis (tool TBD)



                                                                       f"""
                                                                       if test -f Dockerfile; then
                                                                        echo Build started on `date`
                                                                        echo Building the Docker image...
                                                                        docker build -t {core.Aws.ACCOUNT_ID}.dkr.ecr.{core.Aws.REGION}.amazonaws.com/$repoName:$dateStamp-$commitId .
                                                                        echo Build completed on `date`
                                                                        echo Pushing the Docker image to Amazon ECR
                                                                        docker push {core.Aws.ACCOUNT_ID}.dkr.ecr.{core.Aws.REGION}.amazonaws.com/$repoName:$dateStamp-$commitId
                                                                       else
                                                                        echo "There is not a Dockerfile, cannot build"
                                                                       fi
                                                                       """
                                                                   ]}
                                                           },
                                                       }),
                                                       environment=codebuild.BuildEnvironment(
                                                           build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_3,
                                                           privileged=True
                                                       ),
                                                       timeout=core.Duration.minutes(60)
                                                       )
        docker_image_build.on_state_change('ArkCase Docker Image Build Project State Change',
                                           target=events_targets.SnsTopic(
                                               topic=sns_topic,
                                               message=events.RuleTargetInput.from_text(f"Build ID {events.EventField.from_path('$.detail.build-id')} for build project {events.EventField.from_path('$.detail.project-name')} has reached the build status of {events.EventField.from_path('$.detail.build-status')}. Link: {events.EventField.from_path('$.detail.additional-information.logs.deep-link')} ")),
                                           )

        # add IAM policy to the UI NG Build Role to allow it to access CodeArtifact
        docker_image_build.add_to_role_policy(iam.PolicyStatement(effect=iam.Effect.ALLOW,
                                                                  actions=['ecr:GetAuthorizationToken',
                                                                           'ecr:ListImages',
                                                                           'ecr:BatchGetImage',
                                                                           'ecr:GetDownloadUrlForLayer',
                                                                           'ecr:InitiateLayerUpload',
                                                                           'ecr:UploadLayerPart',
                                                                           'ecr:CompleteLayerUpload',
                                                                           'ecr:BatchCheckLayerAvailability',
                                                                           'ecr:PutImage',
                                                                           ],
                                                                  resources=['*']))

        # create ECR repos, with retain
        for repo in repos:
            ecr_repos[repo] = ecr.Repository(self, f'ecr_{repo}',
                                             repository_name=repo,
                                             image_scan_on_push=True
                                             )

            # Add rules to Amazon EventBridge to notify when a container image scan completes.
            ecr_repos[repo].on_event('ECR Event',
                                     target=events_targets.SnsTopic(
                                         topic=sns_topic,
                                         message=events.RuleTargetInput.from_text(
                                             f"{events.EventField.from_path('$.detail-type')} for {events.EventField.from_path('$.detail.repository-name')} with tags {events.EventField.from_path('$.detail.image-tags')} has {events.EventField.from_path('$.detail.scan-status')}")
                                     ),
                                     )

        # create pipelines
            source_output = codepipeline.Artifact()

            pipelines[repo] = codepipeline.Pipeline(self, f'pipeline_{repo}',
                                                    stages=[
                                                        codepipeline.StageProps(stage_name="Source",
                                                                                actions=[
                                                                                    codepipeline_actions.CodeStarConnectionsSourceAction(
                                                                                        connection_arn="arn:aws:codestar-connections:us-east-1:345280441424:connection/d9992729-173c-4f21-aa48-ba39a65198a3",
                                                                                        action_name="GitHub_Source",
                                                                                        owner="ArkCase",
                                                                                        repo=repo,
                                                                                        branch="develop",
                                                                                        variables_namespace='Source',
                                                                                        output=source_output)]),
                                                        codepipeline.StageProps(stage_name="Build",
                                                                                actions=[
                                                                                    codepipeline_actions.CodeBuildAction(
                                                                                        action_name="Docker_Image_Build",
                                                                                        project=docker_image_build,
                                                                                        environment_variables={
                                                                                                    'RepositoryName': {'value': '#{Source.FullRepositoryName}',
                                                                                                                       'type': codebuild.BuildEnvironmentVariableType.PLAINTEXT},
                                                                                                    'FullCommitId': {'value': '#{Source.CommitId}',
                                                                                                                     'type': codebuild.BuildEnvironmentVariableType.PLAINTEXT}
                                                                                        },
                                                                                        input=source_output,
                                                                                    )],
                                                                                ),
                                                    ],
                                                    artifact_bucket=pipelinearkbaseArtifactsBucket
                                                    )
            pipelines[repo].on_state_change('ArkCase Docker Image Pipeline State Change',
                                            target=events_targets.SnsTopic(
                                                topic=sns_topic,
                                                message=events.RuleTargetInput.from_text(f"Execution ID {events.EventField.from_path('$.detail.execution-id')} for pipeline project {events.EventField.from_path('$.detail.pipeline')} has reached the build status of {events.EventField.from_path('$.detail.state')}.  Link: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipelines[repo].pipeline_name}/executions/{events.EventField.from_path('$.detail.execution-id')}/timeline?region=us-east-1 ")),
                                            )
