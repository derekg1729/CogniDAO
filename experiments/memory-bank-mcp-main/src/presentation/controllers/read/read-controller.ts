import { badRequest, notFound, ok, serverError } from "../../helpers/index.js";
import {
  Controller,
  ReadFileUseCase,
  ReadRequest,
  ReadResponse,
  Request,
  Response,
  Validator,
} from "./protocols.js";

export class ReadController implements Controller<ReadRequest, ReadResponse> {
  constructor(
    private readonly readFileUseCase: ReadFileUseCase,
    private readonly validator: Validator
  ) {}

  async handle(request: Request<ReadRequest>): Promise<Response<ReadResponse>> {
    try {
      const validationError = this.validator.validate(request.body);
      if (validationError) {
        return badRequest(validationError);
      }

      const { projectName, fileName } = request.body!;

      const content = await this.readFileUseCase.readFile({
        projectName,
        fileName,
      });

      if (content === null) {
        return notFound(fileName);
      }

      return ok(content);
    } catch (error) {
      return serverError(error as Error);
    }
  }
}
