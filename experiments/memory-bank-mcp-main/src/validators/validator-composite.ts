import { Validator } from "../presentation/protocols/validator.js";

export class ValidatorComposite implements Validator {
  constructor(private readonly validators: Array<Validator>) {}

  validate(input?: any): Error | null {
    for (const validator of this.validators) {
      const error = validator.validate(input);
      if (error) {
        return error;
      }
    }
    return null;
  }
}
