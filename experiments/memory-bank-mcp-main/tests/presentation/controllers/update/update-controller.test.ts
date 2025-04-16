import { describe, expect, it, vi } from "vitest";
import { UpdateRequest } from "../../../../src/presentation/controllers/update/protocols.js";
import { UpdateController } from "../../../../src/presentation/controllers/update/update-controller.js";
import {
  NotFoundError,
  UnexpectedError,
} from "../../../../src/presentation/errors/index.js";
import { makeUpdateFileUseCase, makeValidator } from "../../mocks/index.js";

const makeSut = () => {
  const validatorStub = makeValidator<UpdateRequest>();
  const updateFileUseCaseStub = makeUpdateFileUseCase();
  const sut = new UpdateController(updateFileUseCaseStub, validatorStub);
  return {
    sut,
    validatorStub,
    updateFileUseCaseStub,
  };
};

describe("UpdateController", () => {
  it("should call validator with correct values", async () => {
    const { sut, validatorStub } = makeSut();
    const validateSpy = vi.spyOn(validatorStub, "validate");
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    await sut.handle(request);
    expect(validateSpy).toHaveBeenCalledWith(request.body);
  });

  it("should return 400 if validator returns an error", async () => {
    const { sut, validatorStub } = makeSut();
    vi.spyOn(validatorStub, "validate").mockReturnValueOnce(
      new Error("any_error")
    );
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 400,
      body: new Error("any_error"),
    });
  });

  it("should call UpdateFileUseCase with correct values", async () => {
    const { sut, updateFileUseCaseStub } = makeSut();
    const updateFileSpy = vi.spyOn(updateFileUseCaseStub, "updateFile");
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    await sut.handle(request);
    expect(updateFileSpy).toHaveBeenCalledWith({
      projectName: "any_project",
      fileName: "any_file",
      content: "any_content",
    });
  });

  it("should return 404 if UpdateFileUseCase returns null", async () => {
    const { sut, updateFileUseCaseStub } = makeSut();
    vi.spyOn(updateFileUseCaseStub, "updateFile").mockResolvedValueOnce(null);
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 404,
      body: new NotFoundError("any_file"),
    });
  });

  it("should return 500 if UpdateFileUseCase throws", async () => {
    const { sut, updateFileUseCaseStub } = makeSut();
    vi.spyOn(updateFileUseCaseStub, "updateFile").mockRejectedValueOnce(
      new Error("any_error")
    );
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 500,
      body: new UnexpectedError(new Error("any_error")),
    });
  });

  it("should return 200 if valid data is provided", async () => {
    const { sut } = makeSut();
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
        content: "any_content",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 200,
      body: "File any_file updated successfully in project any_project",
    });
  });
});
