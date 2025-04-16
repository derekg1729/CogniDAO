import { badRequest, notFound, ok, serverError } from "../../helpers/index.js";
import {
  Controller,
  Request,
  RequestValidator,
  Response,
  UpdateFileUseCase,
  UpdateRequest,
  UpdateResponse,
} from "./protocols.js";

export class UpdateController
  implements Controller<UpdateRequest, UpdateResponse>
{
  constructor(
    private readonly updateFileUseCase: UpdateFileUseCase,
    private readonly validator: RequestValidator
  ) {}

  async handle(
    request: Request<UpdateRequest>
  ): Promise<Response<UpdateResponse>> {
    try {
      const validationError = this.validator.validate(request.body);
      if (validationError) {
        return badRequest(validationError);
      }

      const { projectName, fileName, content } = request.body!;

      const result = await this.updateFileUseCase.updateFile({
        projectName,
        fileName,
        content,
      });

      if (result === null) {
        return notFound(fileName);
      }

      return ok(
        `File ${fileName} updated successfully in project ${projectName}`
      );
    } catch (error) {
      return serverError(error as Error);
    }
  }
}
