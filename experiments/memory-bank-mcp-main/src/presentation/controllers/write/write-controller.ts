import { badRequest, ok, serverError } from "../../helpers/index.js";
import {
  Controller,
  Request,
  Response,
  Validator,
  WriteFileUseCase,
  WriteRequest,
  WriteResponse,
} from "./protocols.js";

export class WriteController
  implements Controller<WriteRequest, WriteResponse>
{
  constructor(
    private readonly writeFileUseCase: WriteFileUseCase,
    private readonly validator: Validator
  ) {}

  async handle(
    request: Request<WriteRequest>
  ): Promise<Response<WriteResponse>> {
    try {
      const validationError = this.validator.validate(request.body);
      if (validationError) {
        return badRequest(validationError);
      }

      const { projectName, fileName, content } = request.body!;

      await this.writeFileUseCase.writeFile({
        projectName,
        fileName,
        content,
      });

      return ok(
        `File ${fileName} written successfully to project ${projectName}`
      );
    } catch (error) {
      return serverError(error as Error);
    }
  }
}
