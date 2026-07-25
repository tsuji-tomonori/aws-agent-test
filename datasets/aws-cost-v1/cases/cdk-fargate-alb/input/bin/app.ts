import * as cdk from "aws-cdk-lib";
import { ServiceStack } from "../lib/service-stack";

const app = new cdk.App();
new ServiceStack(app, "EvaluationServiceStack", {
  env: { account: "123456789012", region: "us-east-1" },
});
