import { ListProjectsController } from "../../../../presentation/controllers/list-projects/list-projects-controller.js";
import { makeListProjects } from "../../use-cases/list-projects-factory.js";

export const makeListProjectsController = () => {
  const listProjectsUseCase = makeListProjects();
  return new ListProjectsController(listProjectsUseCase);
};
