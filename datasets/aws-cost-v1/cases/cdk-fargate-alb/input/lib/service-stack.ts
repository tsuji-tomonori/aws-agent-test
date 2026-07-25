import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecsPatterns from "aws-cdk-lib/aws-ecs-patterns";
import { Construct } from "constructs";

export class ServiceStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, "Vpc", {
      natGateways: 0,
      subnetConfiguration: [
        { name: "isolated", subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });
    const cluster = new ecs.Cluster(this, "Cluster", { vpc });

    new ecsPatterns.ApplicationLoadBalancedFargateService(this, "Service", {
      cluster,
      publicLoadBalancer: false,
      desiredCount: 2,
      cpu: 256,
      memoryLimitMiB: 512,
      taskImageOptions: {
        image: ecs.ContainerImage.fromRegistry("public.ecr.aws/nginx/nginx:stable"),
      },
    });
  }
}
