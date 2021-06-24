import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="ark_iac_aws",
    version="0.0.1",

    description="A sample CDK Python app",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "stacks"},
    packages=setuptools.find_packages(where="stacks"),

    install_requires=[
        "aws-cdk.core==1.108.1",
        "aws-cdk.aws_iam==1.108.1",
        "aws-cdk.aws_sns==1.108.1",
        "aws-cdk.aws_sns_subscriptions==1.108.1",
        "aws-cdk.aws_s3==1.108.1",
        "aws-cdk.aws_ecr==1.108.1",
        "aws-cdk.aws_codepipeline==1.108.1",
        "aws-cdk.aws_codepipeline_actions==1.108.1",
        "aws-cdk.aws_codebuild==1.108.1",
        "aws-cdk.aws_events==1.108.1",
        "aws-cdk.aws_events_targets==1.108.1",
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
