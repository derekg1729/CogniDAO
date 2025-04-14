import { ok, serverError } from "../../helpers/index.js";
import {
  Controller,
  ListProjectsResponse,
  ListProjectsUseCase,
  Response,
} from "./protocols.js";

export class ListProjectsController
  implements Controller<void, ListProjectsResponse>
{
  constructor(private readonly listProjectsUseCase: ListProjectsUseCase) {}

  async handle(): Promise<Response<ListProjectsResponse>> {
    try {
      const projects = await this.listProjectsUseCase.listProjects();
      return ok(projects);
    } catch (error) {
      return serverError(error as Error);
    }
  }
}
