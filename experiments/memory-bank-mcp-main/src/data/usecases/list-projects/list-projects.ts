import {
  ListProjectsUseCase,
  Project,
  ProjectRepository,
} from "./list-projects-protocols.js";

export class ListProjects implements ListProjectsUseCase {
  constructor(private readonly projectRepository: ProjectRepository) {}

  async listProjects(): Promise<Project[]> {
    return this.projectRepository.listProjects();
  }
}
