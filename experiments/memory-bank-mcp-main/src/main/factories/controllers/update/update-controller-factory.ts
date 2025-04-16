import { UpdateController } from "../../../../presentation/controllers/update/update-controller.js";
import { makeUpdateFile } from "../../use-cases/update-file-factory.js";
import { makeUpdateValidation } from "./update-validation-factory.js";

export const makeUpdateController = () => {
  const validator = makeUpdateValidation();
  const updateFileUseCase = makeUpdateFile();

  return new UpdateController(updateFileUseCase, validator);
};
