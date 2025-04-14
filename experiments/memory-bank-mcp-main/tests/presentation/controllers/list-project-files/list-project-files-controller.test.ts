import { describe, expect, it, vi } from "vitest";
import { ListProjectFilesController } from "../../../../src/presentation/controllers/list-project-files/list-project-files-controller.js";
import { ListProjectFilesRequest } from "../../../../src/presentation/controllers/list-project-files/protocols.js";
import { UnexpectedError } from "../../../../src/presentation/errors/index.js";
import {
  makeListProjectFilesUseCase,
  makeValidator,
} from "../../mocks/index.js";

const makeSut = () => {
  const validatorStub = makeValidator<ListProjectFilesRequest>();
  const listProjectFilesUseCaseStub = makeListProjectFilesUseCase();
  const sut = new ListProjectFilesController(
    listProjectFilesUseCaseStub,
    validatorStub
  );
  return {
    sut,
    validatorStub,
    listProjectFilesUseCaseStub,
  };
};

describe("ListProjectFilesController", () => {
  it("should call validator with correct values", async () => {
    const { sut, validatorStub } = makeSut();
    const validateSpy = vi.spyOn(validatorStub, "validate");
    const request = {
      body: {
        projectName: "any_project",
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
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 400,
      body: new Error("any_error"),
    });
  });

  it("should call ListProjectFilesUseCase with correct values", async () => {
    const { sut, listProjectFilesUseCaseStub } = makeSut();
    const listProjectFilesSpy = vi.spyOn(
      listProjectFilesUseCaseStub,
      "listProjectFiles"
    );
    const request = {
      body: {
        projectName: "any_project",
      },
    };
    await sut.handle(request);
    expect(listProjectFilesSpy).toHaveBeenCalledWith({
      projectName: "any_project",
    });
  });

  it("should return 500 if ListProjectFilesUseCase throws", async () => {
    const { sut, listProjectFilesUseCaseStub } = makeSut();
    vi.spyOn(
      listProjectFilesUseCaseStub,
      "listProjectFiles"
    ).mockRejectedValueOnce(new Error("any_error"));
    const request = {
      body: {
        projectName: "any_project",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 500,
      body: new UnexpectedError(new Error("any_error")),
    });
  });

  it("should return 200 with files on success", async () => {
    const { sut } = makeSut();
    const request = {
      body: {
        projectName: "any_project",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 200,
      body: ["file1.txt", "file2.txt"],
    });
  });
});
