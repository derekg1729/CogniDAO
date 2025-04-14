import fs from "fs-extra";
import path from "path";
import { FileRepository } from "../../../data/protocols/file-repository.js";
import { File } from "../../../domain/entities/index.js";
/**
 * Filesystem implementation of the FileRepository protocol
 */
export class FsFileRepository implements FileRepository {
  /**
   * Creates a new FsFileRepository
   * @param rootDir The root directory where all projects are stored
   */
  constructor(private readonly rootDir: string) {}

  /**
   * Lists all files in a project
   * @param projectName The name of the project
   * @returns An array of file names
   */
  async listFiles(projectName: string): Promise<File[]> {
    const projectPath = path.join(this.rootDir, projectName);

    const projectExists = await fs.pathExists(projectPath);
    if (!projectExists) {
      return [];
    }

    const entries = await fs.readdir(projectPath, { withFileTypes: true });
    return entries.filter((entry) => entry.isFile()).map((entry) => entry.name);
  }

  /**
   * Loads the content of a file
   * @param projectName The name of the project
   * @param fileName The name of the file
   * @returns The content of the file or null if the file doesn't exist
   */
  async loadFile(
    projectName: string,
    fileName: string
  ): Promise<string | null> {
    const filePath = path.join(this.rootDir, projectName, fileName);

    const fileExists = await fs.pathExists(filePath);
    if (!fileExists) {
      return null;
    }

    const content = await fs.readFile(filePath, "utf-8");
    return content;
  }

  /**
   * Writes a new file
   * @param projectName The name of the project
   * @param fileName The name of the file
   * @param content The content to write
   * @returns The content of the file after writing, or null if the file already exists
   */
  async writeFile(
    projectName: string,
    fileName: string,
    content: string
  ): Promise<File | null> {
    const projectPath = path.join(this.rootDir, projectName);
    await fs.ensureDir(projectPath);

    const filePath = path.join(projectPath, fileName);

    const fileExists = await fs.pathExists(filePath);
    if (fileExists) {
      return null;
    }

    await fs.writeFile(filePath, content, "utf-8");

    return await this.loadFile(projectName, fileName);
  }

  /**
   * Updates an existing file
   * @param projectName The name of the project
   * @param fileName The name of the file
   * @param content The new content
   * @returns The content of the file after updating, or null if the file doesn't exist
   */
  async updateFile(
    projectName: string,
    fileName: string,
    content: string
  ): Promise<File | null> {
    const filePath = path.join(this.rootDir, projectName, fileName);

    const fileExists = await fs.pathExists(filePath);
    if (!fileExists) {
      return null;
    }

    await fs.writeFile(filePath, content, "utf-8");

    return await this.loadFile(projectName, fileName);
  }
}
