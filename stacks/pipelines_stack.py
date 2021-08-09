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

# List of all the repos from GitHub that we are setting up pipelines for
repos = ['ark_base',
         'ark_base_java11_tomcat9',
         'ark_base_java8_tomcat9',
         'ark_base_java8',
         'ark_base_java11',
         'ark_snowbound',
         'ark_activemq',
         'ark_solr',
         'ark_solr_exporter',
         'ark_cloudconfig',
         ]

# List of emails to subscribe to SNS topic notifications (ECR, CodeBuild, and CodePipeline failures)
emails_to_subscribe = ['devops@armedia.com']

# CodeBuild timeout
codebuild_timeout_in_minutes = 60


class PipelinesStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        pipelines = {}
        ecr_repos = {}

        sns_topic = sns.Topic(self, "docker_image_build_sns_topic",
                              display_name="ArkCase Docker Image Build Pipeline notifications")
        for email in emails_to_subscribe:
            sns_topic.add_subscription(sns_subscriptions.EmailSubscription(email))

        pipelinearkbaseArtifactsBucket = s3.Bucket(self, "pipelinearkbaseArtifactsBucket")

        docker_image_build = codebuild.PipelineProject(self, "docker_image_build",
                                                       build_spec=codebuild.BuildSpec.from_object({
                                                           'version': "0.2",
                                                           'phases': {
                                                               'build': {
                                                                   'commands': [
                                                                       "echo Logging in to Amazon ECR...",
                                                                       "$(aws ecr get-login --no-include-email --region ap-south-1)",

                                                                       "echo $RepositoryName",
                                                                       "echo $FullCommitId",
                                                                       "repoName=$(echo $RepositoryName | cut -d/ -f2)",
                                                                       "commitId=$(echo $FullCommitId | cut -c1-7)",
                                                                       "dateStamp=$(date +%Y%m%d)",
                                                                       "echo Repo Name: $repoName",
                                                                       "echo Commit ID: $commitId",
                                                                       "ls",
                                                                       "existingTags=$(aws ecr list-images --repository-name $repoName --output json --query 'imageIds[*].imageTag')",
                                                                       "echo Tags that already exist in this ECR repo: $existingTags"


                                                                       # TODO: Unit tests
                                                                       # TODO: Static Analysis (tool TBD)



                                                                       f"""
                                                                       if test -f Dockerfile; then
                                                                        echo Build started on `date`
                                                                        echo Building the Docker image...
                                                                        docker build -t {core.Aws.ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/$repoName:$dateStamp-$commitId .
                                                                        docker tag {core.Aws.ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/$repoName:$dateStamp-$commitId {core.Aws.ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/$repoName:latest
                                                                        echo Build completed on `date`
                                                                        echo Pushing the Docker image to Amazon ECR
                                                                        docker push {core.Aws.ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/$repoName
                                                                       else
                                                                        echo "There is not a Dockerfile, cannot build"
                                                                       fi
                                                                       """
                                                                   ]}
                                                           },
                                                       }),
                                                       environment=codebuild.BuildEnvironment(
                                                           build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_3,
                                                           privileged=True  # Necessary for CodeBuild to build Docker images
                                                       ),
                                                       timeout=core.Duration.minutes(codebuild_timeout_in_minutes)
                                                       )
        # docker_image_build.on_state_change('ArkCase Docker Image Build Project State Change',
        #                                    event_pattern=events.EventPattern(
        #                                        source=["aws.codebuild"],
        #                                        detail={
        #                                            "build-status": [{"anything-but": ["IN_PROGRESS", "SUCCEEDED"]}],
        #                                        }
        #                                    ),
        #                                    target=events_targets.SnsTopic(
        #                                        topic=sns_topic,
        #                                        message=events.RuleTargetInput.from_text(f"Build ID {events.EventField.from_path('$.detail.build-id')} for build project {events.EventField.from_path('$.detail.project-name')} has reached the build status of {events.EventField.from_path('$.detail.build-status')}. Link: {events.EventField.from_path('$.detail.additional-information.logs.deep-link')} ")),
        #                                    )

        # add IAM policy to the Docker Image Build Role to allow it to access ECR
        docker_image_build.add_to_role_policy(iam.PolicyStatement(effect=iam.Effect.ALLOW,
                                                                  actions=['ecr:GetAuthorizationToken'],
                                                                  resources=['*']))

        docker_image_build.add_to_role_policy(iam.PolicyStatement(effect=iam.Effect.ALLOW,
                                                                  actions=['ecr:ListImages',
                                                                           'ecr:BatchGetImage',
                                                                           'ecr:GetDownloadUrlForLayer',
                                                                           'ecr:InitiateLayerUpload',
                                                                           'ecr:UploadLayerPart',
                                                                           'ecr:CompleteLayerUpload',
                                                                           'ecr:BatchCheckLayerAvailability',
                                                                           'ecr:PutImage'],
                                                                  resources=(
                                                                      [f'arn:aws:ecr:ap-south-1:{core.Aws.ACCOUNT_ID}:repository/hello-world',
                                                                       f'arn:aws:ecr:ap-south-1:{core.Aws.ACCOUNT_ID}:repository/base_centos'] +
                                                                      [f'arn:aws:ecr:ap-south-1:{core.Aws.ACCOUNT_ID}:repository/{repo}' for repo in repos]
                                                                  )))

        # performing the following actions for each repo in the global list at the top of this file
        for repo in repos:
            # create ECR repo, with retain
            ecr_repos[repo] = ecr.Repository(self, f'ecr_{repo}',
                                             repository_name=repo,
                                             image_scan_on_push=True
                                             )

            # Add rules to Amazon EventBridge to notify when a container image scan completes.
            ecr_repos[repo].on_event('ECR Event',
                                     event_pattern=events.EventPattern(
                                         source=["aws.ecr"],
                                         detail_type=["ECR Image Scan"],
                                         detail={
                                             "scan-status": [{"anything-but": "COMPLETE"}],
                                         }
                                     ),
                                     target=events_targets.SnsTopic(
                                         topic=sns_topic,
                                         message=events.RuleTargetInput.from_text(
                                             f"{events.EventField.from_path('$.detail-type')} for {events.EventField.from_path('$.detail.repository-name')} with tags {events.EventField.from_path('$.detail.image-tags')} has {events.EventField.from_path('$.detail.scan-status')}")
                                     ),
                                     )

            # create pipeline
            source_output = codepipeline.Artifact()
            pipelines[repo] = codepipeline.Pipeline(self, f'pipeline_{repo}',
                                                    stages=[
                                                        codepipeline.StageProps(stage_name="Source",
                                                                                actions=[
                                                                                    codepipeline_actions.CodeStarConnectionsSourceAction(
                                                                                        # This connection arn references the GitHub connection that had to be created beforehand manually in the console.
                                                                                        connection_arn=f"arn:aws:codestar-connections:ap-south-1:{core.Aws.ACCOUNT_ID}:connection/d04bc433-9375-45e1-aba6-05844fd22558",
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
                                            event_pattern=events.EventPattern(
                                                source=["aws.codepipeline"],
                                                detail={
                                                    "state": [{"anything-but": ["STARTED", "SUCCEEDED"]}],
                                                }
                                            ),
                                            target=events_targets.SnsTopic(
                                                topic=sns_topic,
                                                message=events.RuleTargetInput.from_text(f"Execution ID {events.EventField.from_path('$.detail.execution-id')} for pipeline project {events.EventField.from_path('$.detail.pipeline')} has reached the status of {events.EventField.from_path('$.detail.state')}.  Link: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipelines[repo].pipeline_name}/executions/{events.EventField.from_path('$.detail.execution-id')}/timeline?region=ap-south-1 ")),
                                            )
