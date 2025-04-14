import { ListProjects } from "../../../data/usecases/list-projects/list-projects.js";
import { FsProjectRepository } from "../../../infra/filesystem/repositories/fs-project-repository.js";
import { env } from "../../config/env.js";

export const makeListProjects = () => {
  const projectRepository = new FsProjectRepository(env.rootPath);
  return new ListProjects(projectRepository);
};
