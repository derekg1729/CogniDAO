import { ListProjectsUseCase } from "../../../src/domain/usecases/list-projects.js";

export class MockListProjectsUseCase implements ListProjectsUseCase {
  async listProjects(): Promise<string[]> {
    return ["project1", "project2"];
  }
}

export const makeListProjectsUseCase = (): ListProjectsUseCase => {
  return new MockListProjectsUseCase();
};
