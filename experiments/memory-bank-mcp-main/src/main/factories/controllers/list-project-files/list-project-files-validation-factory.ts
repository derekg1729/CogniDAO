import { Validator } from "../../../../presentation/protocols/validator.js";
import { ValidatorComposite } from "../../../../validators/validator-composite.js";

const makeValidations = (): Validator[] => {
  return [];
};

export const makeListProjectFilesValidation = (): Validator => {
  const validations = makeValidations();
  return new ValidatorComposite(validations);
};
