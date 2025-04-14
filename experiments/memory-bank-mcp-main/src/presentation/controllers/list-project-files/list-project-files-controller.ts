import { badRequest, ok, serverError } from "../../helpers/index.js";
import {
  Controller,
  ListProjectFilesRequest,
  ListProjectFilesResponse,
  ListProjectFilesUseCase,
  Request,
  Response,
  Validator,
} from "./protocols.js";

export class ListProjectFilesController
  implements Controller<ListProjectFilesRequest, ListProjectFilesResponse>
{
  constructor(
    private readonly listProjectFilesUseCase: ListProjectFilesUseCase,
    private readonly validator: Validator
  ) {}

  async handle(
    request: Request<ListProjectFilesRequest>
  ): Promise<Response<ListProjectFilesResponse>> {
    try {
      const validationError = this.validator.validate(request.body);
      if (validationError) {
        return badRequest(validationError);
      }

      const { projectName } = request.body!;

      const files = await this.listProjectFilesUseCase.listProjectFiles({
        projectName,
      });

      return ok(files);
    } catch (error) {
      return serverError(error as Error);
    }
  }
}
