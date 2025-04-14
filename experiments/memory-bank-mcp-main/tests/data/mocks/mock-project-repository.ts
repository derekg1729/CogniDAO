import { ProjectRepository } from "../../../src/data/protocols/project-repository.js";
import { Project } from "../../../src/domain/entities/project.js";

export class MockProjectRepository implements ProjectRepository {
  private projects = ["project-1", "project-2"];

  async listProjects(): Promise<Project[]> {
    return this.projects;
  }

  async projectExists(name: string): Promise<boolean> {
    return this.projects.includes(name);
  }

  async ensureProject(name: string): Promise<void> {
    if (!this.projects.includes(name)) {
      this.projects.push(name);
    }
  }
}
