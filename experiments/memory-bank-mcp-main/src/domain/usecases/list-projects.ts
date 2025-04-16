import { Project } from "../entities/index.js";

export interface ListProjectsUseCase {
  listProjects(): Promise<Project[]>;
}
