import { ReadController } from "../../../../presentation/controllers/read/read-controller.js";
import { makeReadFile } from "../../use-cases/read-file-factory.js";
import { makeReadValidation } from "./read-validation-factory.js";

export const makeReadController = () => {
  const validator = makeReadValidation();
  const readFileUseCase = makeReadFile();

  return new ReadController(readFileUseCase, validator);
};
