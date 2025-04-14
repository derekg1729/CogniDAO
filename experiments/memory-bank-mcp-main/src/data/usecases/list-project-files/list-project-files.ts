import {
  FileRepository,
  ListProjectFilesParams,
  ListProjectFilesUseCase,
  ProjectRepository,
} from "./list-project-files-protocols.js";

export class ListProjectFiles implements ListProjectFilesUseCase {
  constructor(
    private readonly fileRepository: FileRepository,
    private readonly projectRepository: ProjectRepository
  ) {}

  async listProjectFiles(params: ListProjectFilesParams): Promise<string[]> {
    const { projectName } = params;
    const projectExists = await this.projectRepository.projectExists(
      projectName
    );

    if (!projectExists) {
      return [];
    }

    return this.fileRepository.listFiles(projectName);
  }
}
