import { ListProjectsUseCase } from "../../../domain/usecases/list-projects.js";
import { Controller, Response } from "../../protocols/index.js";

export type ListProjectsResponse = string[];

export { Controller, ListProjectsUseCase, Response };
