import { WriteController } from "../../../../presentation/controllers/write/write-controller.js";
import { makeWriteFile } from "../../use-cases/write-file-factory.js";
import { makeWriteValidation } from "./write-validation-factory.js";

export const makeWriteController = () => {
  const validator = makeWriteValidation();
  const writeFileUseCase = makeWriteFile();

  return new WriteController(writeFileUseCase, validator);
};
