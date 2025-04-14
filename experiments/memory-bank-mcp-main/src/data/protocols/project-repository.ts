import { Project } from "../../domain/entities/index.js";

export interface ProjectRepository {
  listProjects(): Promise<Project[]>;
  projectExists(name: string): Promise<boolean>;
  ensureProject(name: string): Promise<void>;
}
