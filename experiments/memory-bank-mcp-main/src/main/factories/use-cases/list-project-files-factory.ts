import { ListProjectFiles } from "../../../data/usecases/list-project-files/list-project-files.js";
import { FsFileRepository } from "../../../infra/filesystem/index.js";
import { FsProjectRepository } from "../../../infra/filesystem/repositories/fs-project-repository.js";
import { env } from "../../config/env.js";

export const makeListProjectFiles = () => {
  const projectRepository = new FsProjectRepository(env.rootPath);
  const fileRepository = new FsFileRepository(env.rootPath);

  return new ListProjectFiles(fileRepository, projectRepository);
};
