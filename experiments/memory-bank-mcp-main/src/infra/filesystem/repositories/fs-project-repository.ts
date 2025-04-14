import fs from "fs-extra";
import path from "path";
import { ProjectRepository } from "../../../data/protocols/project-repository.js";
import { Project } from "../../../domain/entities/index.js";

/**
 * Filesystem implementation of the ProjectRepository protocol
 */
export class FsProjectRepository implements ProjectRepository {
  /**
   * Creates a new FsProjectRepository
   * @param rootDir The root directory where all projects are stored
   */
  constructor(private readonly rootDir: string) {}

  /**
   * Builds a path to a project directory
   * @param projectName The name of the project
   * @returns The full path to the project directory
   * @private
   */
  private buildProjectPath(projectName: string): string {
    return path.join(this.rootDir, projectName);
  }

  /**
   * Lists all available projects
   * @returns An array of Project objects
   */
  async listProjects(): Promise<Project[]> {
    const entries = await fs.readdir(this.rootDir, { withFileTypes: true });
    const projects: Project[] = entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name);

    return projects;
  }

  /**
   * Checks if a project exists
   * @param name The name of the project
   * @returns True if the project exists, false otherwise
   */
  async projectExists(name: string): Promise<boolean> {
    const projectPath = this.buildProjectPath(name);
    // If path doesn't exist, fs.stat will throw an error which will propagate
    const stat = await fs.stat(projectPath);
    return stat.isDirectory();
  }

  /**
   * Ensures a project directory exists, creating it if necessary
   * @param name The name of the project
   */
  async ensureProject(name: string): Promise<void> {
    const projectPath = this.buildProjectPath(name);
    await fs.ensureDir(projectPath);
  }
}
